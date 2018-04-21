#!/usr/bin/env python

from os.path import exists, join, abspath
from os import pathsep
from time import strftime
import sys, errno
from string import split
import json
import argparse
import logging, logging.handlers
from urlparse import urljoin

# Add libreelec distro-specific path for requests
sys.path.append('/storage/.kodi/addons/script.module.requests/lib/')
import requests
      
# Add libreelec distro-specific path for BeautifulSoup
sys.path.append('/storage/.kodi/addons/script.module.beautifulsoup4/lib/')
from bs4 import BeautifulSoup

import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

import magic

# ------------------------------

class Config:
   """ Configuration class.

   Load configuration from a file - search a path list to find the file.
   """

   def __init__(self, filename, path = '.'):
      """Constructor."""
      
      self.config_filename = filename
      self.search_path = path
      pass

   def __del__(self):
      """Destructor."""
      pass

   # Find a file in a given path list
   def search_file(self, filename, search_path):
      """Given a search path, find file
      """
      file_found = 0
      paths = search_path.split(pathsep)
      for path in paths:
         if exists(join(path, filename)):
            file_found = 1
            break
      if file_found:
         return abspath(join(path, filename))
      else:
         return None

   def load_config(self):
      cfile = self.search_file(self.config_filename, self.search_path)
      if cfile:
         with open(cfile, 'r') as f:
            config = json.load(f)
            return config
      else:
         raise IOError(errno.ENOENT, 'No config file found on path', self.search_path)

      return None

# ------------------------------

class Extractor:
   """ Extract a part of a web page and either print it or email it somewhere.

   Used for extracting comic images to distribute via email.
   """

   def __init__(self, config):
      """Constructor."""

      self.config = config
      self.cache = {}
      pass

   def __del__(self):
      """Destructor."""
      pass

   def get_part(self, name):
      target = self.config['extractors'][name]
      
      # Check cache first
      if name in self.cache:
         logger.debug('Cache hit for %s', name)
         return self.cache[name]
      
      self.request = requests.get(target['URL'])
      soup = BeautifulSoup(self.request.text, 'html.parser')
      try:
	  part = soup.select_one(target['Xtor'])
      except ValueError, e:
	  logger.error('Error with extraction. %s', e)
	  logger.error('Xtor is: %s', target['Xtor'])
	  return None, None

      img = None
      try:
         ptype = part.name
         logger.debug('get_part: Got %s, contents: %s', ptype, part)

         if ptype == 'img':
            if 'src' in part.attrs:
               part['src'] = urljoin(target['URL'], part['src'])
            elif 'data-src' in part.attrs:
               part['src'] = urljoin(target['URL'], part['data-src'])
            part = requests.get(part['src']).content
      except AttributeError, e:
         return None, None

      # Add part to cache
      self.cache[name] = (ptype, part)
      
      return ptype, part

   def extract(self, name):
      (ptype, part) = self.get_part(name)
      return part

   def email(self, names, recips, message):

      msg = MIMEMultipart('related')
      msg.preamble = 'This is a multi-part message in MIME format.'
      msgAlt = MIMEMultipart('alternative')
      msg.attach(msgAlt)
      if message:
         pre_text = message + "\n"
         pre_html = '<p>%s<p><br />' % message
      else:
         pre_text = pre_html = ''
      
      index = 1
      for name in names:
         (ptype, part) = self.get_part(name)
         if ptype == None:
            next
         elif ptype == 'img':
            pre_html += '<img src="cid:img%02d" alt="%s" width="100%%"><br /><br />' % (index, name.encode('utf-8'))
	    try:
		img = MIMEImage(part)
	    except TypeError, e:
		logger.error('Can\'t determine image type. %s', e)
		logger.error('Name is: %s', name)
		logger.debug('Data: %s', part)
		logger.error('Retrying using the magic library.')
		try:
		    m = magic.detect_from_content(part)
		    img = MIMEImage(part, m.mime_type)
		except TypeError, e:
		    logger.error('Determining image type failed again, aborting.')
		    img = None
	    if(img):
		img.add_header('Content-ID', '<img%02d>' % index)
		msg.attach(img)
         else:
            pre_text += "\n" + part.get_text().encode('utf-8')
            pre_html += part.encode('utf-8')
         index = index + 1

      pre_text += "\nComics brought to you by suex.py, on the RaspberryPi3!"
      pre_html += '<hr /><p>Comics brought to you by suex.py, on the RaspberryPi3!</p>'
      msgAlt.attach(MIMEText(pre_text))
      msgAlt.attach(MIMEText(pre_html, 'html'))
      
      msg['Subject'] = 'Comics of the day - ' + strftime('%B %d, %Y')
      msg['From'] = '%s <%s>' % (self.config['mail_from_name'], self.config['mail_from'])
      if len(recips) == 1:
         msg['To'] = ', '.join(recips)
      else:
         msg['To'] = 'undisclosed-recipients:;'

      logger.info('Sending email to %s', ', '.join(recips))
      s = smtplib.SMTP(self.config['smtp_server'])
      s.starttls()
      (retval, retstr) = s.login(self.config['smtp_user'], self.config['smtp_pass'])
      logger.debug('SMTP login. %s', retstr)
      try:
         errs = s.sendmail(self.config['mail_from'], recips, msg.as_string())
         if len(errs):
            logger.error('The following recipients did not receive the email. %s', ', '.join(errs))
      except SMTPRecipientsRefused, e:
         logger.error('Recipients refused. %s', e)
      except SMTPHeloError, e:
         logger.error('HELO error. %s', e)
      except SMTPSenderRefused, e:
         logger.error('Sender refused. %s', e)
      except SMTPDataError, e:
         logger.error('Data error. %s', e)
      
      s.quit()
      return None


def optimize_recipients(recips):
   """ Return an optimized list where each list of recipients has the same
   list of comics
   """

   logging.debug('optimize_recipients start')
   
   res = []

   # Go through every recipient to find a match or not in the res list
   for eaddr in recips:
      hit = 0
      for target in res:
         if set(recips[eaddr]) == set(target[1]):
            # Add key to existing target list
            target[0].append(eaddr)
            hit = 1
      if not hit:
         res.append(([eaddr], recips[eaddr]))

   logging.debug('optimize_recipients end, res = %s', res)
      
   return res


# ------------------------------

if __name__ == '__main__':
   # logging.basicConfig(filename='suex.log',level=logging.DEBUG)

   # Set up a specific logger with our desired output level
   logger = logging.getLogger()
   logger.setLevel(logging.INFO)

   # Add the log message handler to the logger
   handler = logging.handlers.TimedRotatingFileHandler('suex.log', when='d', interval=7, backupCount=3)

   logger.addHandler(handler)


   logger.info('Starting on %s, parsing args', strftime('%B %d, %Y'))
   parser = argparse.ArgumentParser()
   group = parser.add_mutually_exclusive_group(required=True)
   group.add_argument('-a', '--all', help='run extractor on all configured entries', action='store_true')
   group.add_argument('-r', '--recipient', help='run extractor for specified subscriber')
   group.add_argument('-x', '--extract', help='extract specific entry to stdout (for testing extractor)')
   parser.add_argument('-m', '--message', help='add custom message to email')
   # parser.add_argument('-e', '--email', action='append', help='email address(es) to use')
   parser.add_argument('-v', '--version', action='version', version='%(prog)s 1.0')
   args = parser.parse_args()

   search_path = pathsep.join(['/usr/local/etc', '/etc', '/storage', '.'])
   try:
      xconfig = Config('suex_config.json', search_path).load_config()
   except IOError, e:
      # print >> sys.stderr, 'suex_config.json:', e
      logger.critical('suex_config.json: %s', e)
      sys.exit(-3)
   
   try:
      sconfig = Config(xconfig['subscriber_config'], search_path).load_config()
   except IOError, e:
      # print >> sys.stderr, xconfig['subscriber_config'] + ':', e
      logger.critical('%s: %s', xconfig['subscriber_config'], e)
      sys.exit(-3)

   logger.info('Loaded config files. Subscriber config is %s', xconfig['subscriber_config'])

   recips = optimize_recipients(sconfig)


   try:
      e = Extractor(xconfig)
   except IOError, err:
      # print >> sys.stderr, err
      logger.critical(err)
      sys.exit(-1)

# --- All entries ------------------------

   if args.all:
      logger.debug('Processing all subscriber entries.')
      for entry in recips:

         try:
            e.email(entry[1], entry[0], args.message)
         except KeyError, err:
            # print >> sys.stderr, 'Unknown/unsupported page extraction:', err
            logger.error('Unknown/unsupported page extraction: %s', err)
            # sys.exit(-2)
            continue

# --- Specific subscriber ----------------

   elif args.recipient:
      logger.debug('Processing for subscriber %s.', args.recipient)
      if args.recipient not in sconfig:
         print >> sys.stderr, 'Recipient "%s" not defined.' % args.recipient
         logger.critical('Recipient "%s" not defined.', args.recipient)
         sys.exit(-4)
      try:
         e.email(sconfig[args.recipient], [args.recipient], args.message)
      except KeyError, err:
         print >> sys.stderr, 'Unknown/unsupported page extraction:', err
         logger.critical('Unknown/unsupported page extraction: %s', err)
         sys.exit(-2)


# --- Specific extractor -----------------

   elif args.extract:
      logger.debug('Processing for extractor %s.', args.extract)
      print e.extract(args.extract)
