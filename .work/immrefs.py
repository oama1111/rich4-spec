import sys,subprocess,re
out=subprocess.run(['python3','tools/scratch/r4dump.py',sys.argv[1],sys.argv[2]],capture_output=True,text=True).stdout
for l in out.splitlines():
    for m in re.finditer(r'0x(4[6-9a-f][0-9a-f]{4})',l):
        v=int(m.group(1),16)
        if 0x463000<=v<0x46c000 or 0x474000<=v<0x476000 or 0x47e000<=v<0x480000 or 0x482300<=v<0x482400 or 0x48b000<=v<0x48c000:
            print(l.strip(), '   <=', hex(v))
            break
