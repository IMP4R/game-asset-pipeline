import subprocess,psutil,time,sys
p=subprocess.Popen(sys.argv[1:]);start=time.monotonic();peak=0
while p.poll() is None:
 try:
  proc=psutil.Process(p.pid);rss=sum(c.memory_info().rss for c in [proc]+proc.children(recursive=True));peak=max(peak,rss)
  if rss>1900*1024**2 or time.monotonic()-start>150:
   for c in proc.children(recursive=True):c.kill()
   p.kill();print('STOP: budget limit');break
 except psutil.NoSuchProcess:break
 time.sleep(.1)
print('Peak monitored MiB:',round(peak/1024**2,1));sys.exit(p.wait())
