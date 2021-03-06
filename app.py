# -*- coding: utf-8 -*-
"""
@title:       arowf - accuracy review of wikipedias (in) flask.
@description: Registration-free open source text-based blind review system.
@author:      Priyanka Mandikal and Jim Salsman.
@version:     0.9 prebeta of August 15, 2016.
@license:     Apache v2 or latest with stronger patent sharing if available.
@see:     https://github.com/priyankamandikal for previous and subsequent versions.
###@@@: means places that I want to continue working on;
###: introduces comments that involve lower-priority work to be done
"""

import sys
reload(sys)
sys.setdefaultencoding("utf-8")

from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask.ext.bootstrap import Bootstrap     # bootstrap templates 
from flask.ext.mail import Mail, Message      # email sending
from threading import Thread                  # to send asynchronous emails
from passlib.hash import pbkdf2_sha512        # for creatung tokens
from os import listdir, rename, path, environ # for path.sep, .exists() & .getmtime()
from random import choice                     # chosing a random question file
from time import ctime                        # file analysis in inspect()
from re import compile, match, sub            # for url and token matching
from pickle import dump, load                 # for storing dict of username and token for redundancy checking
from datetime import date, datetime           # for logging
from collections import OrderedDict           # to store question types in the order of modification times

recdir = 'records' + path.sep                 # data subdirectory

urlregex = compile(r'((https|ftp|http)://(((?!</p>| )).)*)')
###@@@ make sure this handles unicode and parens

maxinspect = 20  ###@@@ (TODO below:) how many done to /inspect

### question type/search question: do we need question types beyond as
### they can be described with their own strings inside the question?
### If not, will HTML comments work for non-displayed codes?

app = Flask(__name__) # create Flask WSGI application
app.config['SECRET_KEY'] = environ.get('SECRET_KEY')

# mail configuration settings
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = environ.get('MAIL_PASSWORD')
app.config['AROWF_MAIL_SUBJECT_PREFIX'] = '[AROWF]'
app.config['AROWF_MAIL_SENDER'] = 'AROWF Admin'
app.config['AROWF_ADMIN'] = environ.get('AROWF_ADMIN')

bootstrap = Bootstrap(app)  # create Bootstrap instance
mail = Mail(app)            # create Mail instances


def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)


def send_email(to, subject, template, **kwargs):
    msg = Message(app.config['AROWF_MAIL_SUBJECT_PREFIX'] + ' ' + subject,
                  sender=app.config['AROWF_ADMIN'], recipients=[to])
    msg.body = render_template(template + '.txt', **kwargs)
    msg.html = render_template(template + '.html', **kwargs)
    thr = Thread(target=send_async_email, args=[app, msg])
    thr.start()
    return thr


@app.route('/')
def index():
    return render_template('index.html')          # in templates subdirectory


def linkandescape(txt):
    # substitute urls with tokens, remembering them in a list
    urls = []
    def match1(mo):
        urls.append(mo.group(0).replace('"', '%22')) # hexify quotation marks
        return '###URL-TOKEN-' + str(len(urls)) + '###'
    substed = sub(urlregex, match1, txt)
    # replace '&' with '&amp;' and '<' with '&lt;'
    escaped = substed.replace('&', '&amp;').replace('<', '&lt;')
    # replace URL tokens with <a href="url">url</a> links
    def match2(mo):
        url = urls[int(mo.group(1))-1]
        return '<a href="' + url + '">' + url + '</a>' 
    return sub(regex2, match2, escaped)
regex2 = compile(r'###URL-TOKEN-([1-9][0-9]*)###')


def frameurl(url):
    # check if iframeurl matches the urlregexp
    if match(urlregex, url):
        qurl = url.replace('"', '%22') # hexify quotation marks
        # if so, return indented html to display it as an iframe
        return '\n\n<br/>\n<iframe src="' + qurl \
                + '" style="height: 40%; width:100%">' \
                + '[Can not display <a href="' + qurl + '">' + qurl \
                + '</a> inline as an iframe here.]</iframe>i' \
                + '<br\>\n'
    else:
        return ''


def nextrecord():
    try:
        # search files in the records subdirectory to find the greatest number
        records = listdir(recdir)
        record = 1+int(max(records)[0:9])  # increment maximum
        ### todo: check for improperly named files        
        return format(record, '09')        # left-pad with zeros to 9 places
    except:
        return format(1, '09')             # first is 1, not 0


@app.route('/register', methods=['GET', 'POST'])
def register():
    with open('users.pkl', 'r') as f:
        userdict = load(f)
    if request.method == 'GET':
        logdate = datetime.strftime(date.today(), '%Y-%m-%d')
        logfn = './logs/activity-'+logdate
        user = 'Anonymous'                      # Username is Anonymous by default
        if 'token' in session:
            token = session['token']
            tokenfilename = 'registered/'+token
            with open(tokenfilename, 'r') as f: # for getting username associated with the set token
                user = f.readline()[:-1]
        with open(logfn, 'a') as f:     # logging username, IP addr, end-point, request type
            log = user+' '+request.environ['REMOTE_ADDR']+' register'+' GET\n'
            f.write(log)
        return render_template('register.html', userdict=userdict) # inputs for name, email, timezone, phone, aboutme
    elif request.method == 'POST':
        uname = str(request.form['uname'])      # mandatory
        email = str(request.form['email'])      # mandatory
        timezone = request.form['timezone']     # optional
        phone = request.form['phone']           # optional
        aboutme = request.form['aboutme']       # optional
        token = pbkdf2_sha512.encrypt(email)    # setting the token as a salted and hashed email
        token = token.replace('/', '+')         # filenames can't contain '/'
        session['token'] = token                # set token in session key on successful registration
        fn = 'registered' + path.sep + token
        with open(fn, 'w') as f:                # write reviewer info into a file named by the token
            f.write(uname+'\n'+email+'\n'+timezone+'\n'+phone+'\n'+aboutme+'\n')
            f.write('--files--\n')
        userdict[uname] = email
        with open('users.pkl', 'w') as f:       # dictionary with keys as usernames and values as emails
            dump(userdict, f)
        send_email(email, 'Welcome to AROWF!', 'registration_mail', name=uname, token=token)    # send welcome email with token
        logdate = datetime.strftime(date.today(), '%Y-%m-%d')
        logfn = './logs/activity-'+logdate
        with open(logfn, 'a') as f:     # logging username, IP addr, end-point, request type
            log = uname+' '+request.environ['REMOTE_ADDR']+' register'+' POST\n'
            f.write(log)
        return redirect(url_for('index'))


@app.route('/ask', methods=['GET', 'POST'])
def ask():
    if request.method == 'GET':
        logdate = datetime.strftime(date.today(), '%Y-%m-%d')
        logfn = './logs/activity-'+logdate
        user = 'Anonymous'                      # Username is Anonymous by default
        if 'token' in session:
            token = session['token']
            tokenfilename = 'registered/'+token
            with open(tokenfilename, 'r') as f: # for getting username associated with the set token
                user = f.readline()[:-1]
        with open(logfn, 'a') as f:     # logging username, IP addr, end-point, request type
            log = user+' '+request.environ['REMOTE_ADDR']+' ask'+' GET'+'\n'
            f.write(log)
        return render_template('ask.html') # single textarea & submit button
    elif request.method == 'POST':
        question = linkandescape(request.form['question'])
        question = question + frameurl(request.form['iframeurl'])
        ### sanity-check size of question field
        qn_number = nextrecord()
        fn = 'records' + path.sep + qn_number + 'q' # new question filename
        # checking if the file exists should prevent overflow(?)
        if path.exists(fn):
            flash('Overflow: a billion questions is too many; sorry.')
            return redirect(url_for('index'))          # GET /
            ### RACE condition if two people call nextrecord() simultaniously
            ### ... maybe try adding the process ID to end of fn and renaming?
        with open(fn, 'w') as f:
            f.write(question+'\n') ### only add \n if not already at end? & below
            if 'token' in session:
                f.write('--REGISTRATION-ID:'+session['token']+'--')
        logdate = datetime.strftime(date.today(), '%Y-%m-%d')
        logfn = './logs/activity-'+logdate
        user = 'Anonymous'                      # Username is Anonymous by default
        if 'token' in session:
            token = session['token']
            tokenfilename = 'registered/'+token
            with open(tokenfilename, 'r') as f: # for getting username associated with the set token
                user = f.readline()[:-1]
        with open(logfn, 'a') as f:     # logging username, IP addr, end-point, request type, question number
            log = user+' '+request.environ['REMOTE_ADDR']+' ask'+' POST '+qn_number+'\n'
            f.write(log)
        if 'token' in session:
            userfile = 'registered/'+session['token']
            if path.exists(fn):
                with open(userfile, 'a') as f:
                    f.write(fn[8:]+'\n')
        flash('Thanks for the question.')  # displays in layout.html
        return redirect(url_for('index'))  # GET /


def getrecords():
    records = {} # use a dictionary of file numbers to lists of suffixes
    for fn in listdir(recdir):             ### handle bad filenames
        if not fn[0:9] in records:
            records[fn[0:9]] = [fn[9]]     # create file number's initial list
        else:
            records[fn[0:9]].append(fn[9]) # add file suffix to list
    return records


@app.route('/answer', methods=['GET', 'POST'])
def answer():
    if request.method == 'GET':
        records = getrecords()
        selected = {}
        for ns, l in records.items():       # iterate over filenumbers
            if ns in selected or 'd' in l:  #   and filename suffix [l]ist
                continue                    # already did this filenumber
            elif not 'a' in l:
                selected[ns] = 'a'          # question needs an answer
            elif not ('e' in l or 'o' in l):
                selected[ns] = 'r'          # answer needs review
            elif 'o' in l and not 't' in l:
                selected[ns] = 't'          # opposing review needs tie-breaker
        if len(selected) < 1:
            flash('No open questions remaining to answer or review.')
            return redirect(url_for('index'))
        chosen = choice(selected.keys())    # pick a question at random
        needs = selected[chosen]            # type of response needed
        files = {}                          # files' contents in a suffix
        for suffix in records[chosen]:      # iterate over the files available
            with open(recdir + chosen + suffix, 'r') as f:
                files[suffix] = sub(r'--REGISTRATION-ID:.*--$', '', f.read())        # read textual contents of each
        logdate = datetime.strftime(date.today(), '%Y-%m-%d')
        logfn = './logs/activity-'+logdate
        user = 'Anonymous'                      # Username is Anonymous by default
        if 'token' in session:
            token = session['token']
            tokenfilename = 'registered/'+token
            with open(tokenfilename, 'r') as f: # for getting username associated with the set token
                user = f.readline()[:-1]
        with open(logfn, 'a') as f:     # logging username, IP addr, end-point, request type, question number, required answer
            log = user+' '+request.environ['REMOTE_ADDR']+' answer'+' GET'+' '+chosen+' '+needs+'\n'
            f.write(log)
        return render_template('answer.html', record=chosen, response=needs,
                               files=files) # invoke the template
    elif request.method == 'POST':
        record = request.form['record']     # file number with zeroes
        response = request.form['response'] # [submit button] 1 of: a,e,o,te,to
        answer = linkandescape(request.form['answer'])
        answer = answer + frameurl(request.form['iframeurl'])
        ### sanity-check size
        if response in ['te', 'to']:        # tie breaker
            if path.exists(recdir + record + 't'):
                flash('Someone else just submitted that tiebreaker.')
                return redirect(url_for('index'))
                ###@@@ SLOW RACE: see below
            rename(recdir + record + 'o', recdir + record + 't')
            response = response[1]          # 2nd character
        fn = recdir + record + response     # filename ### sanity check?
        if path.exists(fn):                 # does file exist?
            flash('Someone else just submitted the requested response.')
            return redirect(url_for('index'))
            ###@@@ SLOW RACE: lock choice() responses below for some time?
        with open(fn, 'w') as f:
            f.write(answer+'\n') ### only add \n if not already at end?
            if 'token' in session:
                f.write('--REGISTRATION-ID:'+session['token']+'--')
        logdate = datetime.strftime(date.today(), '%Y-%m-%d')
        logfn = './logs/activity-'+logdate
        user = 'Anonymous'                      # Username is Anonymous by default
        if 'token' in session:
            token = session['token']
            tokenfilename = 'registered/'+token
            with open(tokenfilename, 'r') as f: # for getting username associated with the set token
                user = f.readline()[:-1]
        with open(logfn, 'a') as f:    # logging username, IP addr, end-point, request type, question number, given answer 
            log = user+' '+request.environ['REMOTE_ADDR']+' answer'+' POST'+' '+record+' '+response+'\n'
            f.write(log)
        if 'token' in session:
            userfile = 'registered/'+session['token']
            if path.exists(fn):
                with open(userfile, 'a') as f:
                    f.write(fn[8:]+'\n')
        flash('Thank you for your response.') # displays in layout.html
        return redirect(url_for('index'))


@app.route('/recommend', methods=['GET', 'POST'])
def recommend():
    if request.method == 'GET':
        records = getrecords()              # populated dictionary
        selected = {}                       # empty dictionary (hash table)
        for ns, l in records.items():       # iterate over keys and values 
            if ns in selected or 'd' in l:  # already seen filenumber or done
                continue                    # skip when already done
            elif 'e' in l or 't' in l:      # endorsed or tie-broken
                selected[ns] = l            # add list as a dictionary entry
        if len(selected) < 1:
            flash('No recommendations remain to be implemented.')
            return redirect(url_for('index'))
        selection = choice(selected.keys()) # pick a random reviewed question
        suffixes = selected[selection]
        files = {}                              # to map file suffixes to text
        for suffix in suffixes:                 # iterate over available files
            with open(recdir + selection + suffix, 'r') as f:
                files[suffix] = sub(r'--REGISTRATION-ID:.*--$', '', f.read())            # read textual contents of each
        logdate = datetime.strftime(date.today(), '%Y-%m-%d')
        logfn = './logs/activity-'+logdate
        user = 'Anonymous'                      # Username is Anonymous by default
        if 'token' in session:
            token = session['token']
            tokenfilename = 'registered/'+token
            with open(tokenfilename, 'r') as f: # for getting username associated with the set token
                user = f.readline()[:-1]
        with open(logfn, 'a') as f: # logging username, IP addr, end-point, request type, question number
            log = user+' '+request.environ['REMOTE_ADDR']+' recommend'+' GET '+selection+'\n'
            f.write(log)
        return render_template('recommend.html', record=selection, files=files) 
    elif request.method == 'POST':
        record = request.form['record']         # file num. w/zeroes ### check
        resolution = linkandescape(request.form['resolution']) # implementation
        resolution = resolution + frameurl(request.form['iframeurl'])
        ### sanity-check size of resolution field
        fn = recdir + record + 'd'              # resolution filename
        if path.exists(fn):                     # does file exist?
            flash('Someone else just submitted another implementation.')
            return redirect(url_for('index'))
            ###@@@ SLOW RACE: see above
        with open(fn, 'w') as f:
            f.write(resolution+'\n') ### only add \n if not already at end?
            if 'token' in session:
                f.write('--REGISTRATION-ID:'+session['token']+'--')
        records = getrecords()
        modtime = {}                # file modification times for question types
        for l in records[record]:
            modtime[l] = path.getmtime(recdir+record+l)
        od = OrderedDict(sorted(modtime.items(), key=lambda t: t[1]))
        logdate = datetime.strftime(date.today(), '%Y-%m-%d')
        logfn1 = './logs/activity-'+logdate
        user = 'Anonymous'                      # Username is Anonymous by default
        if 'token' in session:
            token = session['token']
            tokenfilename = 'registered/'+token
            with open(tokenfilename, 'r') as f: # for getting username associated with the set token
                user = f.readline()[:-1]
        with open(logfn1, 'a') as f: # logging username, IP addr, end-point, request type, question number in activities
            log = user+' '+request.environ['REMOTE_ADDR']+' recommend'+' POST '+record+'\n'
            f.write(log)
        logfn2 = './logs/results-'+logdate
        with open(logfn2, 'a') as f: # logging question number, types and mod times of all related files in the order of creation in results
            f.write(record+' ')
            for qntype, mtime in od.items():
                log = qntype+' '+datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')+' '
                f.write(log)
            f.write('\n')
        if 'token' in session:
            userfile = 'registered/'+session['token']
            if path.exists(fn):
                with open(userfile, 'a') as f:
                    f.write(fn[8:]+'\n')
        flash('Thank you for the implementation.') # displays in layout.html
        return redirect(url_for('index'))


def mintime(v):
    if len(v) > 0:
        return ctime(min(v))
    else:
        return 'n/a'


def maxtime(v):
    if len(v) > 0:
        return ctime(max(v))
    else:
        return 'n/a'


@app.route('/inspect', methods=['GET']) # optional: ?q=searchstring&r=reviewer
def inspect():
    records = getrecords()
    if len(records) < 1:
        flash('No questions in system.')
        return redirect(url_for('index'))
    filenums = records.keys()              # assuming contiguity can't delete
    filemodtimes = []                      # all file modification times
    searchstring = request.args.get('q')   # search e.g. category in -q files
    stringtimes = {'q':[],'a':[],'e':[],'o':[],'t':[],'d':[]} # searchstring
    reviewer = request.args.get('r')       # search for reviewer in -a/e/o/t
    reviewtimes = {'a':[],'e':[],'o':[],'t':[]} # times for reviewer search
    reviewercount = 0                      # number of times reviewer appears
    revieweragree = 0                      # times reviewer was agreed with
    reviewerdised = 0                      # times reviewer was opposed
    for fn in filenums:
        stringhit = False                  # flag whether searchstring is seen
        if searchstring:
            f = open(recdir + fn + 'q', 'r') # check question files
            question = f.read()
            f.close()
            if searchstring.lower() in question.lower():   # substring search
                stringhit = True           # question has string
        for suffix in records[fn]:         # iterate over the files available
            modtime = path.getmtime(recdir + fn + suffix) # file modification
            filemodtimes.append(modtime)
            if stringhit:
                stringtimes[suffix].append(modtime)
            if reviewer and suffix in ['a', 'e', 'o', 't']:
                with open(recdir + fn + suffix, 'r') as f:
                    contents = f.read()        # look for the reviewer argument
                if reviewer in contents:         # substring search
                    reviewercount = reviewercount + 1
                    reviewtimes[suffix].append(modtime) # store time
                    if suffix == 'a':            # reviewer answered
                        if 'e' in records[fn]:   # answer endorsed
                            revieweragree = revieweragree + 1
                        elif 'o' in records[fn]: # answer opposed
                            reviewerdised = reviewerdised + 1
                    elif suffix == 't':          # opposition was tiebroken
                        if 'o' in records[fn]:   # opposition agreed to
                            revieweragree = revieweragree + 1
                        elif 'e' in records[fn]: # opposition rejected
                            reviewerdised = reviewerdised + 1

    ### last N with -d files by their date
    done = {}                                # -d cmodtime -> filenumber
    if 'd' in records[fn]:
        fndtime = path.getmtime(recdir + fn + 'd')
        if len(done) < maxinspect:
            done[fndtime] = fn
        else:
            if fndtime >= max(done.keys()):
                del done[min(done.keys())]
                done[fndtime] = fn
    showdone = '' ### html
    #for fn in done.values().sort():          # show latest in -q order
    #    showdone = showdone + ###@@@
    pass

    # summary statistics
    count, first, last = len(records), min(filenums), max(filenums)
    mindate, maxdate = min(filemodtimes), max(filemodtimes)
    if len(filemodtimes) > 0:
        meandate = ctime(sum(filemodtimes) / len(filemodtimes))
    else:
        meandate = 'n/a'
        
    denom = revieweragree + reviewerdised   # agreement ratio
    if denom > 0:
        ratio='%2.0f%%' % (((revieweragree+0.0) / denom) * 100)
    else:
        ratio='n/a'

    logdate = datetime.strftime(date.today(), '%Y-%m-%d')
    logfn = './logs/activity-'+logdate
    user = 'Anonymous'                      # Username is Anonymous by default
    if 'token' in session:
        token = session['token']
        tokenfilename = 'registered/'+token
        with open(tokenfilename, 'r') as f: # for getting username associated with the set token
            user = f.readline()[:-1]
    if searchstring == None:
        searchstring = ''
    if reviewer == None:
        reviewer = ''
    with open(logfn, 'a') as f:     # logging username, IP addr, end-point, request type, #searchstring#, #reviewer#
        log = user+' '+request.environ['REMOTE_ADDR']+' inspect'+' GET #'+searchstring+'# #'+reviewer+'#\n'
        f.write(log)

    return render_template('inspect.html', count=count, first=first, \
        last=last, mindate=ctime(mindate), maxdate=ctime(maxdate), \
        meandate=meandate, searchstring=searchstring, \
        stringqs=len(stringtimes['q']), \
        sqmn=mintime(stringtimes['q']), sqmx=maxtime(stringtimes['q']), \
        stringas=len(stringtimes['a']), \
        samn=mintime(stringtimes['a']), samx=maxtime(stringtimes['a']), \
        stringes=len(stringtimes['e']), \
        semn=mintime(stringtimes['e']), semx=maxtime(stringtimes['e']), \
        stringos=len(stringtimes['o']), \
        somn=mintime(stringtimes['o']), somx=maxtime(stringtimes['o']), \
        stringts=len(stringtimes['t']), \
        stmn=mintime(stringtimes['t']), stmx=maxtime(stringtimes['t']), \
        stringds=len(stringtimes['d']), \
        sdmn=mintime(stringtimes['d']), sdmx=maxtime(stringtimes['d']), \
        reviewer=reviewer, revas=len(stringtimes['a']), \
        reves=len(stringtimes['e']), revos=len(stringtimes['o']), \
        revts=len(stringtimes['t']), reviewercount=reviewercount, \
        revieweragree=revieweragree, reviewerdised=reviewerdised, \
        ratio=ratio, showdone=showdone)


@app.route('/help')
def help():
    return render_template('help.html') # displays links to help docs for each end-point


@app.route('/token', methods=['GET', 'POST'])
def token():
    if request.method == 'GET':
        logdate = datetime.strftime(date.today(), '%Y-%m-%d')
        logfn = './logs/activity-'+logdate
        user = 'Anonymous'                      # Username is Anonymous by default
        if 'token' in session:
            token = session['token']
            tokenfilename = 'registered/'+token
            with open(tokenfilename, 'r') as f: # for getting username associated with the set token
                user = f.readline()[:-1]
        with open(logfn, 'a') as f:     # logging username, IP addr, end-point, request type
            log = user+' '+request.environ['REMOTE_ADDR']+' token'+' GET\n'
            f.write(log)
        tokenNames = listdir('registered/')         # get list of all tokens
        return render_template('token.html', user=user, tokenNames=tokenNames) # displays links to help docs for each end-point
    elif request.method == 'POST':                  # if token not set in session key
        if request.form['tokeninput'] != 'null':
            session['token'] = request.form['tokeninput']    # obtain from form and set it
        else:
            session.pop('token', None)
        logdate = datetime.strftime(date.today(), '%Y-%m-%d')
        logfn = './logs/activity-'+logdate
        user = 'Anonymous'                      # Username is Anonymous by default
        if 'token' in session:
            token = session['token']
            tokenfilename = 'registered/'+token
            with open(tokenfilename, 'r') as f: # for getting username associated with the set token
                user = f.readline()[:-1]
        with open(logfn, 'a') as f:     # logging username, IP addr, end-point, request type
            log = user+' '+request.environ['REMOTE_ADDR']+' token'+' POST\n'
            f.write(log)
        return redirect(url_for('index'))


@app.errorhandler(404)
def page_not_found(error):
    logdate = datetime.strftime(date.today(), '%Y-%m-%d')
    logfn = './logs/activity-'+logdate
    user = 'Anonymous'                      # Username is Anonymous by default
    if 'token' in session:
        token = session['token']
        tokenfilename = 'registered/'+token
        with open(tokenfilename, 'r') as f: # for getting username associated with the set token
            user = f.readline()[:-1]
    with open(logfn, 'a') as f:     # logging username, IP addr, error code
        log = user+' '+request.environ['REMOTE_ADDR']+' 404\n'
        f.write(log)
    return render_template('404.html'), 404


@app.errorhandler(500)
def page_not_found(error):
    logdate = datetime.strftime(date.today(), '%Y-%m-%d')
    logfn = './logs/activity-'+logdate
    user = 'Anonymous'                      # Username is Anonymous by default
    if 'token' in session:
        token = session['token']
        tokenfilename = 'registered/'+token
        with open(tokenfilename, 'r') as f: # for getting username associated with the set token
            user = f.readline()[:-1]
    with open(logfn, 'a') as f:     # logging username, IP addr, error code
        log = user+' '+request.environ['REMOTE_ADDR']+' 500\n'
        f.write(log)
    return render_template('500.html'), 500


# No cache
@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = 0
    return response


if __name__ == '__main__':
    app.run(
      use_reloader = True # reloads this source file when changed
     , use_debugger=True
     , debug = environ.get('DEBUGGER') # see http://flask.pocoo.org/docs/0.11/errorhandling/
           )                    # runs on http://127.0.0.1:5000/

# end
