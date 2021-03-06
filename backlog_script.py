import requests
from bs4 import BeautifulSoup
import traceback
from os import path, listdir

url = 'https://en.wikipedia.org/wiki/Category:Wikipedia_articles_in_need_of_updating_from_May_2016'
categ = path.basename(url)

recdir = 'records' + path.sep

def nextrecord():
	try:
		records = listdir(recdir)
		record = 1+int(max(records)[:9])
		### todo: check for improperly named files
		return format(record, '09')
	except:
		return format(1, '09')

if __name__ == '__main__':

	try:
		r = requests.get(url)
		bs = BeautifulSoup(r.text)
		cnt = 0;
		for catgroup in bs.find_all('div', 'mw-category-group'):
			for entry in catgroup.find_all('li'):
				a = entry.find('a')
				link = 'https://en.wikipedia.org' + a.get('href')
				title = a.get('title').encode('utf8')
				fn = recdir + nextrecord() + 'q'
				print fn
				if path.exists(fn):
					print('A billion questions reached! Answer!')
					exit()
				f = open(fn, 'w')
				f.write('The article <a href="' + link + '">' + title + '</a> is in ' + categ + '.</br>How would you update it?<br/><a style="float:right;" href="'+link+'">'+link+'</a><iframe src="' + link + '" style="height: 40%; width: 100%;">[Can not display <a href="' + link + '">' + link + '</a> inline as an iframe here.]</iframe>')
				#f.write(categ + '\n' + title + '\n' + link +'\n')	# in file, print <backlog category>, <title>, <link>
				f.close()
				cnt = cnt+1
				if(cnt==5):
					exit()

	except:
		print "Error while parsing backlogs"
		print traceback.format_exc()
