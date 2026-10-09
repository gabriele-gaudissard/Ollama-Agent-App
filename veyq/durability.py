"""Bounded, local task state and context checkpoints; never replay uncertain writes."""
import copy
import json
import time


def compact(session, limit):
    history = session['history']
    eligible = [i for i, m in enumerate(history) if m.get('role') == 'user']
    cut = 0
    while len(json.dumps(history[cut:])) > limit and len(eligible) > 2:
        eligible.pop(0)
        cut = eligible[0]
    if cut:
        notes = [session.get('context_summary', '')]
        previous = min(session.get('context_offset', 0), cut)
        for message in history[previous:cut]:
            role = message.get('role')
            content = str(message.get('content', ''))
            if role == 'user':
                notes.append('User request: ' + content[:1200])
            elif role == 'tool':
                notes.append('Observed tool ' + message.get('name', '') + ': ' + content[:800])
            elif role == 'assistant' and content:
                notes.append('Earlier assistant statement (verify before relying on it): ' + content[:400])
        session['context_summary'] = '\n'.join(notes)[-10000:]
        session['context_offset'] = cut
    result = copy.deepcopy(history[cut:])
    for message in result:
        if message.get('role') == 'tool' and len(message.get('content', '')) > 5000:
            message['content'] = message['content'][:5000] + '\n[Earlier output shortened; inspect the source again when needed.]'
    # A long single task can contain many tool exchanges without a new user turn.
    # Replace whole completed exchanges; preserve requests and the recent tail.
    while len(json.dumps(result)) > limit:
        index = next((i for i, m in enumerate(result[:-4]) if m.get('role') == 'assistant' and m.get('tool_calls')), None)
        if index is None:
            index = next((i for i, m in enumerate(result[:-4]) if m.get('role') == 'assistant' and not m.get('tool_calls')), None)
            if index is None: break
            result.pop(index)
            continue
        ids = {c['id'] for c in result[index]['tool_calls']}
        end = index + 1
        while end < len(result) and result[end].get('role') == 'tool' and result[end].get('tool_call_id') in ids: end += 1
        if {m.get('tool_call_id') for m in result[index+1:end]} != ids: break
        note = 'Earlier tool observations (verify before reuse): ' + '; '.join(m.get('name', '') + ': ' + str(m.get('content', ''))[:350] for m in result[index+1:end])
        result[index:end] = [{'role': 'assistant', 'content': note[:1500]}]
    return result


def checkpoint(session, state, **values):
    session['task'] = {**session.get('task', {}), **values, 'state': state, 'updated_at': time.time()}


def recover(session):
    task = session.get('task', {})
    if task.get('state') in {'running', 'approval', 'question'}:
        checkpoint(session, 'interrupted')
    # A crash after dispatch may leave assistant tool calls without results.
    # Preserve the pair and explicitly mark its outcome unknown, never replay it.
    history = session.get('history', [])
    answered = {m.get('tool_call_id') for m in history if m.get('role') == 'tool'}
    repaired = []
    for message in history:
        repaired.append(message)
        for call in message.get('tool_calls', []):
            if call.get('id') not in answered:
                repaired.append({'role': 'tool', 'tool_call_id': call['id'], 'name': call.get('function', {}).get('name', ''),
                                 'content': json.dumps({'ok': False, 'outcome_unknown': True,
                                     'error': 'Application stopped before recording this result. Inspect the actual state before any retry; the action may already have happened.'})})
                answered.add(call['id'])
    session['history'] = repaired
