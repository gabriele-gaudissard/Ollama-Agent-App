"""Veyq desktop launcher."""
import os
import sys
from veyq.desktop import DesktopAPI, main

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, str(error), 'Veyq - Avvio non riuscito', 0x10)
        else:
            print(str(error), file=sys.stderr)
        sys.exit(1)
