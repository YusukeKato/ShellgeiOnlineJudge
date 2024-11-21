#!/usr/bin/env python3
import sys
import subprocess
import asyncio
import time

async def main(cid):
  try:
    result = await asyncio.wait_for(shellgei(cid), timeout=5)
    print(result)
  except asyncio.TimeoutError:
    print("!!time out!!")

async def shellgei(cid):
  result = subprocess.run(['sudo', 'docker', 'exec', cid, '/bin/bash', '-c','./z.bash'], encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  return result.stdout

args = sys.argv
cid = args[1]
asyncio.run(main(cid))
