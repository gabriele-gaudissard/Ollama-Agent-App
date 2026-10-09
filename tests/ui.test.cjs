"use strict";
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const path = require("node:path");
const { JSDOM } = require("jsdom");
const root = path.resolve(__dirname, "..");
const dom = new JSDOM(fs.readFileSync(path.join(root,"index.html"),"utf8"),{url:"https://veyq.test",runScripts:"outside-only",pretendToBeVisual:true});
const w=dom.window,document=w.document;
const dispose=w.close.bind(w);
const calls=[];
let eventState={events:[],busy:false,state:"idle"};
let voiceState={state:'idle',ready:true};
const chatRows=[{id:"demo",title:"New activity",untitled:true,project_id:""},{id:"other",title:"Second chat",project_id:""}];
const settings={lang:"en",model:"qwen3:14b",provider:"local",permission:"auto",network:true,auto_update:false,workspace:"C:\\Demo",setup_completed:true,max_steps:0,command_timeout:0,github_repo:"",data_dir:"C:\\Demo",has_provider_token:false,has_github_token:false};
w.matchMedia=()=>({matches:true});w.confirm=()=>true;w.prompt=()=>"Renamed";
Object.defineProperty(w.navigator,"clipboard",{value:{writeText:async text=>calls.push(["clipboard",text])}});
const api={
 voice_status:async()=>voiceState,start_voice:async()=>{calls.push(['startVoice']);voiceState={state:'recording',ready:true,started_at:Date.now()/1000};},stop_voice:async()=>{calls.push(['stopVoice']);voiceState={state:'completed',ready:true,text:'Dictated message'};},cancel_voice:async()=>{calls.push(['cancelVoice']);voiceState={state:'idle',ready:true};},prepare_voice:async()=>calls.push(['prepareVoice']),
 get_task_overview:async()=>({task:{state:'interrupted',goal:'<img src=x onerror=alert(1)>',progress:'Verified a file',next_steps:'Read it again'},procedures:[{name:'coding',purpose:'Implement and verify code'}],automations:[{id:'job',prompt:'<script>unsafe</script>',interval_hours:24,enabled:true,last_state:'pending'}]}),
 review_changes:async()=>({diff:'-old\n+<img src=x onerror=alert(1)>\n'}),
 resume_task:async id=>calls.push(['resume',id]),save_automation:async(...args)=>calls.push(['schedule',...args]),
 toggle_automation:async id=>calls.push(['toggleSchedule',id]),remove_automation:async id=>calls.push(['removeSchedule',id]),
 get_tool_catalog:async()=>({total:30,groups:[{name:'Mouse and keyboard',description:'Inspect Windows applications, click, double-click, right-click, drag, scroll, type and change keyboard layouts.',count:5}]}),
 delete_session:async id=>{calls.push(["delete",id]);const i=chatRows.findIndex(s=>s.id===id);if(i>=0)chatRows.splice(i,1);},
 create_session:async()=>{calls.push(["create"]);const id="created";chatRows.push({id,title:"New activity",untitled:true,project_id:""});return id;},
 get_settings:async()=>({...settings}),get_sessions:async()=>chatRows,get_projects:async()=>[{id:"project-one",name:"Project one"}],
 get_session:async id=>({id,workspace:"C:\\Demo",history:id==="other"?[{role:"user",content:"Other conversation"}]:[],plan:[]}),get_events:async()=>eventState,
 assign_project:async(id,project)=>{calls.push(["assign",id,project]);chatRows.find(s=>s.id===id).project_id=project;},
 get_model_catalog:async()=>({models:[{name:"sample:7b",weight:"Light",download_gb:4,uses:"General writing, analysis and lightweight tool tasks"}],hardware:{ram_gb:16,disk_free_gb:100}}),
 get_models:async()=>({ok:true,models:["qwen3:14b","llama3.2:3b"]}),set_language:async lang=>{settings.lang=lang;calls.push(["language",lang]);},
 get_model_info:async name=>({name,installed:true,metadata_origin:"Installed engine metadata",parameters:"14.8B",quantization:"Q4_K_M",context_tokens:40960,tools:true,vision:false,hardware:{ram_gb:32,disk_free_gb:100},ram_min_gb:16,ram_recommended_gb:24,source:"https://ollama.com/library/qwen3:14b"}),
 follow_up:async(...args)=>calls.push(["followup",...args]),stop_run:async()=>calls.push(["stop"]),
 answer_question:async(...args)=>calls.push(["answer",...args]),
 get_memory:async()=>"Preference",save_memory:async text=>calls.push(["memory",text]),
 open_external:async url=>calls.push(["link",url]),
};
w.pywebview={api};
const context=dom.getInternalVMContext();
for(const file of ["i18n.js","assets/vendor/marked.js","assets/vendor/purify.js","assets/vendor/highlight.js","app.js"])
 new vm.Script(fs.readFileSync(path.join(root,file),"utf8"),{filename:file}).runInContext(context);
const tick=()=>new Promise(resolve=>setTimeout(resolve,30));
(async()=>{
 w.dispatchEvent(new w.Event("pywebviewready"));await tick();
 const body=w.message("assistant",'# Heading\n\n**Bold**\n\n|A|B|\n|-|-|\n|1|2|\n\n```python\nprint("ok")\n```\n\n<script>alert(1)</script><img src="x" onerror="alert(1)"><form><input></form>\n\n[bad](javascript:alert(1))');
 assert.equal(body.querySelector("h1").textContent,"Heading");assert.ok(body.querySelector("strong"));assert.ok(body.querySelector("table"));assert.ok(body.querySelector(".hljs"));
 assert.equal(body.querySelectorAll("script,img,form,input,iframe").length,0);
 assert.equal(body.querySelector("a").hasAttribute("href"),false);
 body.closest("article").querySelector(".message-actions button").click();await tick();
 assert.match(calls.find(c=>c[0]==="clipboard")[1],/\*\*Bold\*\*/);
 w.renderText(body,"Updated streaming text");assert.equal(body.closest("article").dataset.raw,"Updated streaming text");
 const original=body.textContent;
 for(const lang of ["it","es","fr","en"]){w.VeyqI18N.setLanguage(lang);await tick();assert.equal(document.documentElement.lang,lang);assert.equal(body.textContent,original);}
 assert.equal(document.getElementById("saveSettings").textContent,"Save settings");
 await w.showSettings();await tick();
 assert.equal(document.getElementById("maxSteps").value,"0");
 assert.equal(document.getElementById("timeout").value,"0");
 assert.equal(document.getElementById("githubRepo").value,"");
 assert.equal(document.getElementById("providerToken").placeholder,"Token (optional for the local engine)");
 await w.showTaskCenter();await tick();
 assert.equal(document.getElementById('resumeTask').disabled,false);
 assert.match(document.getElementById('taskProgress').textContent,/<img/);
 assert.equal(document.querySelector('#taskProgress img'),null);
 document.getElementById('reviewChanges').click();await tick();
 assert.equal(document.querySelectorAll('#changesPreview .diff-add').length,1);
 assert.equal(document.querySelector('#changesPreview img'),null);
 for(const lang of ['it','es','fr']){w.VeyqI18N.setLanguage(lang);await tick();assert.notEqual(document.querySelector('#taskModal h2').textContent,'Task center');assert.notEqual(document.querySelector('#executionEnvironment option[value=sandbox]').textContent,'Offline sandbox — disposable project copy');}
 w.VeyqI18N.setLanguage('en');await tick();
 document.getElementById('automationPrompt').value='Read source';document.getElementById('automationHours').value='2';document.getElementById('createAutomation').click();await tick();
 assert.deepEqual(calls.find(c=>c[0]==='schedule'),['schedule','demo','Read source',2]);
 document.querySelector('#procedureList button').click();await tick();assert.match(document.getElementById('prompt').value,/coding/);document.getElementById('prompt').value='';
 w.close('taskModal');
 document.getElementById('voiceButton').click();await tick();await w.pollVoice();
 assert.match(document.getElementById('voiceStatus').textContent,/Recording locally/);
 document.getElementById('voiceButton').click();await tick();await w.pollVoice();
 assert.match(document.getElementById('prompt').value,/Dictated message/);
 assert.ok(calls.some(c=>c[0]==='cancelVoice'));document.getElementById('prompt').value='';
 document.getElementById('voiceButton').click();await tick();await w.loadSession('other');
 assert.equal(voiceState.state,'idle');assert.equal(document.getElementById('cancelVoice').hidden,true);await w.loadSession('demo');
 assert.equal(document.getElementById("githubToken").placeholder,"Token with access to the repositories you need");
 for(const lang of ["it","es","fr"]){w.VeyqI18N.setLanguage(lang);await tick();assert.notEqual(document.getElementById("providerToken").placeholder,"Token (optional for the local engine)");}
 w.VeyqI18N.setLanguage("en");await tick();
 await w.showTools();assert.match(document.getElementById('toolCatalog').textContent,/Mouse and keyboard/);w.close('toolsModal');
 w.VeyqI18N.setLanguage('it');await tick();await w.showTools();assert.match(document.getElementById('toolCatalog').textContent,/Mouse e tastiera/);assert.doesNotMatch(document.getElementById('toolCatalog').textContent,/Inspect Windows/);w.close('toolsModal');w.VeyqI18N.setLanguage('en');await tick();
 assert.equal(document.getElementById("providerToken").placeholder,"Token (optional for the local engine)");
 settings.has_provider_token=true;settings.has_github_token=true;await w.showSettings();await tick();
 assert.equal(document.getElementById("providerToken").placeholder,"Saved in vault; leave blank to keep it");
 assert.equal(document.getElementById("githubToken").placeholder,"Saved in vault; leave blank to keep it");
 w.setBusy(true);assert.match(document.getElementById("send").textContent,/Stop/);
 document.getElementById("prompt").value="Continue with a test";document.getElementById("prompt").dispatchEvent(new w.Event("input"));
 assert.match(document.getElementById("send").textContent,/follow-up/);await w.send();assert.ok(calls.some(c=>c[0]==="followup"));
 await w.send();assert.ok(calls.some(c=>c[0]==="stop"));w.setBusy(false);
 document.getElementById("toggleActivity").click();await tick();assert.ok(document.querySelector(".shell").classList.contains("activity-mobile-open"));
 document.getElementById("closeActivity").click();await tick();assert.equal(document.querySelector(".shell").classList.contains("activity-mobile-open"),false);
 await w.showCatalog();assert.equal(document.querySelectorAll(".model-card").length,1);
 assert.equal(document.querySelector(".model-name button").textContent,"ⓘ");
 assert.equal(document.getElementById("catalogChoice").options.length,2);
 assert.equal(document.getElementById("modelInfo").parentElement,document.getElementById("model").parentElement);
 await w.showModelInfo("qwen3:14b");assert.match(document.getElementById("modelInfoContent").textContent,/14.8B/);assert.match(document.getElementById("modelInfoContent").textContent,/40,960|40.960/);
 w.close("modelInfoModal");w.close("catalogModal");w.close("settingsModal");
 // Switching conversations while streaming must neither block navigation nor leak text.
 eventState={events:[{seq:1,session_id:"demo",type:"text",data:{text:"Active partial"}}],session_id:"demo",busy:true,state:"running"};await w.poll();
 assert.ok([...document.querySelectorAll(".session")].every(b=>!b.disabled));
 await w.loadSession("other");assert.match(document.getElementById("messages").textContent,/Other conversation/);assert.doesNotMatch(document.getElementById("messages").textContent,/Active partial/);
 assert.match(document.getElementById("send").textContent,/Return to active/);
 eventState.events=[{seq:2,session_id:"demo",type:"text",data:{text:" continued"}}];await w.poll();
 await w.loadSession("demo");assert.match(document.getElementById("messages").textContent,/Active partial continued/);
 eventState={events:[{seq:3,session_id:"demo",type:"done",data:{}}],session_id:"demo",busy:false,state:"completed"};await w.poll();
 assert.ok([...document.querySelectorAll(".session,.session-more")].every(b=>!b.disabled));
 await w.loadSession("other");await w.loadSession("demo");
 // Menu assignment must target that chat, even if another chat is selected.
 const otherRow=[...document.querySelectorAll(".session-row")].find(r=>r.textContent.includes("Second chat"));
 otherRow.querySelector(".session-more").click();[...otherRow.querySelectorAll(".session-menu button")].find(b=>b.textContent==="Add to project").click();await tick();
 document.getElementById("chatProjectChoice").value="project-one";document.getElementById("saveChatProject").click();await tick();
 assert.deepEqual(calls.find(c=>c[0]==="assign"),["assign","other","project-one"]);
 w.showQuestion({id:"q1",question:"Which project?",options:["One","Two"]});document.querySelector("#questionOptions button").click();document.getElementById("submitAnswer").click();await tick();
 assert.deepEqual(calls.find(c=>c[0]==="answer"),["answer","q1","One"]);
 document.getElementById("language").value="it";document.getElementById("language").dispatchEvent(new w.Event("change"));await tick();assert.equal(settings.lang,"it");assert.equal(document.querySelector(".session span").textContent,"Nuova attività");
 const dictionaries=w.VeyqI18N.dictionaries;
 for(const [key,value] of Object.entries(dictionaries.strings))for(const lang of ["it","es","fr"])assert.ok(value[lang],key+":"+lang);
 assert.equal(new Set([...document.querySelectorAll("[id]")].map(e=>e.id)).size,document.querySelectorAll("[id]").length);
 await w.loadSession("other");const beforeDelete=chatRows.length;
 document.getElementById("deleteChat").click();await tick();
 assert.equal(chatRows.length,beforeDelete-1);assert.ok(!chatRows.some(s=>s.id==="other"));
 assert.equal(calls.filter(c=>c[0]==="create").length,0);assert.ok(document.querySelector(".session.active"));
 document.getElementById("deleteChat").click();await tick();
 assert.equal(chatRows.length,0);assert.equal(document.querySelectorAll(".session").length,0);assert.equal(document.querySelectorAll(".message").length,0);
 assert.equal(document.getElementById("welcome").hidden,false);assert.equal(calls.filter(c=>c[0]==="create").length,0);
 w.dispatchEvent(new w.Event("pywebviewready"));await tick();assert.equal(chatRows.length,0);assert.equal(calls.filter(c=>c[0]==="create").length,0);
 console.log("UI checks passed, including actual removal of chats and no replacement empty chat after deletion/restart.");
 dispose();
})().catch(error=>{console.error(error);dispose();process.exitCode=1;});
