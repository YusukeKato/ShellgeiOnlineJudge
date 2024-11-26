#!/usr/bin/env python3
import sys
import re

args = sys.argv
output = args[1]
output_image = args[2]
answer = args[3]
answer_image = args[4]

#output = re.sub('\r', '', output)
#answer = re.sub('\r', '', answer)
while re.match(r'.*NEWLINE$', output) != None:
  output = re.sub(r'NEWLINE$', '', output)
while re.match(r'.*NEWLINE$', answer) != None:
  answer = re.sub(r'NEWLINE$', '', answer)
while re.match(r'.*\r$', output) != None:
  output = re.sub(r'\r$', '', output)
while re.match(r'.*\r$', answer) != None:
  answer = re.sub(r'\r$', '', answer)
output_image = output_image[28:]
answer_image = answer_image[28:]

judge = "0"
if (output == answer and output_image == answer_image):
  judge = "1"
elif (output == answer and output_image != answer_image):
  judge = "2"
elif (output != answer and output_image == answer_image):
  judge = "3"
else:
  judge = "4"
print(judge)

# debug
f = open('../debug.txt', 'w', encoding='UTF-8')
f.write('output: '+output+'\n')
f.write('answer: '+answer+'\n')
f.write('output_len: '+str(len(output))+'\n')
f.write('answer_len: '+str(len(answer))+'\n')
f.write('output_image: '+output_image+'\n')
f.write('answer_image: '+answer_image+'\n')
f.write('output_image_len: '+str(len(output_image))+'\n')
f.write('answer_image_len: '+str(len(answer_image))+'\n')
f.write('judge: '+judge+'\n')
f.close()
