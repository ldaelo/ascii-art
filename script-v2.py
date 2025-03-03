from types import SimpleNamespace as namespace
from base64 import urlsafe_b64encode
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from pathvalidate import sanitize_filename
from glob import glob
from json import load
from PIL import Image
from math import ceim
import os, numpy as np

root = '/storage/emulated/0/ascii-art2'

with open(os.path.join(root, 'ascii-dict-v4.json')) as d:
	ad = json.load(d)

subject = max(glob.glob(os.path.join(root, 'subjects', '*')), key=os.path.getmtime)
title = input('Title: ')
caption = input('Caption: ')

adk, adv = ad.keys(), np.array(list(ad.values()))

fs = 16 # font size
fr = 3 / 5 #font aspect ratio
fw, fh = math.ceil(fs * fr), fs #font width, font height
_4K = 1_920 #frame size

font = namespace(width=10, height=16)
frame = namespace(ratio=(16, 9), size=240)

with Image.open(subject) as im:
	
	ratio = namespace()
	ratio.width, ratio.height = frame.ratio
	
	image = namespace()
	image.width, image.height = im.size
	
	if image.width < image.height:
		ratio.width, ratio.height = min(frame.ratio), max(frame.ratio)
	elif image.width > image.height:
		ratio.width, ratio.height = max(frame.ratio), min(frame.ratio)
	
	ratio.ratio = ratio.width / ratio.height
	image.ratio = image.width / image.height
	
	image.crop = namespace()
	image.crop.width = image.width
	image.crop.height = image.height
	
	if image.ratio > ratio.ratio:
		image.crop.width = image.crop.height * ratio.ratio // ratio.width * ratio.width
	else:
		image.crop.height = image.crop.width / ratio.ratio // ratio.height * ratio.height
	
	image.crop.x = (image.width - image.crop.width) // 2
	image.crop.y = (image.height - image.crop.height) // 2
	
	im = im.crop((
		image.crop.x,
		image.crop.y,
		image.crop.x + image.crop.width,
		image.crop.y + image.crop.height
	)).im.resize((ratio.width * frame.size, ratio.height * frame.size), Image.NEAREST)
	
	output = namespace()
	output.cols, output.rows = im.size
	output.cols //= font.width
	output.rows //= font.height
	
	data = namespace(data=np.array(im.resize((output.cols * 2, output.rows * 2), Image.BOX).convert('L')))

data.range = namespace(min=np.min(data.data), max=np.max(data.data))
data.range._100 = data.range.max - data.range.min

output.output = np.full((output.rows, output.cols), '', dtype=object)
process = namespace(progress=0, cache={})

def progress():
	while True:
		print('%d%% (%d/%d) completed' % (round(process.progress / data.data.size * 100), process.progress, data.data.size))
		if process.progress == data.data.size: break
		sleep(1)

def worker(x, y, xx, yy):
	block = data.data[yy : yy + 2, xx : xx + 2]
	hash = bytes(block)
	if hash in process.cache:
		output.output[y][x] = process.cache[hash]
		return
	dict_values = [np.linalg.norm((block - data.range.min) / data.range._100 - char) for char in ascii_dict.values]
	result = dict(zip(dict_values, ascii_dict.keys))[np.min(dict_values)]
	output.output[y][x] = result
	process.cache[hash] = result

def proxy(args):
	try: worker(*args)
	except Exception as err: print(err)
	process.progress += 1

Thread(target=progress).start()

print('generating ascii art...')
with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
	executor.map(proxy, [(x, y, x * 2, y * 2) for y in range(output.rows) for x in range(output.cols)])

output.string = '\n'.join(''.join(line) for line in output.output)
output.files = namespace()

print('creating html...')

output.files.html = '%s-%s.html' % (sanitize_filename(title), urlsafe_b64encode(os.urandom(3)).decode())

with open(os.path.join(root, fn), 'w') as o:
	
	title_html = html.escape(title)
	output_html = html.escape(output)
	caption_html = html.escape(caption)
	
	o.write('''<!DOCTYPE html>
<html lang="en">
<head>
<base href="https://ldaelo.github.io/ascii-art/">
<meta charset="UTF-8">
<title>ASCII Art: %s</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<figure>
  <pre role="img">%s</pre>
  <figcaption>
    <h1>%s</h1>
    <h2>%s</h2>
    <p>donate via PayPal (<a href="https://www.paypal.me/paelom">paelom</a>) or GCash (09076598998 Paelo Moldes)</p>
    <hr>
    <div class="license">
      <p>This work is licensed under the <a href="https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.en">CC BY-NC-ND 4.0 License</a>.</p>
      <a href="https://creativecommons.org/licenses/by-nc-nd/4.0/legalcode.en"><img src="by-nc-nd.png" alt="CC BY-NC-ND 4.0 License"></a>
    </div>
  </figcaption>
</figure>
</body>
</html>''' % (title_html, output_html, title_html, caption_html))

print('html saved to', fn)