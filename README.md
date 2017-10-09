# webitem-extractor
Extract parts of web pages (eg. comics) and optionally email them.


## History
It all started years ago with a perl script which used regular expressions
to extract parts of web pages and email them. It was used to extract things
like the quote at the bottom of the [Slashdot](https://slashdot.org/) page,
or Edward de Bono's [Message for Today](http://www.debonothinking.com/).

Over time the script became more sophisticated, becoming more DOM aware and
able to extract images (from various comic strips). At one point the script
was rewritten in Ruby (as a way to learn that language), and now it is written
in Python. In this latest version, there is now a separate configuration file
which defines the items that can be extracted and how to achieve that, and 
a separate "subscribers" file which describes who gets what items. Both of
these files are JSON formatted files.

In all this, the name of the original script has been preserved - "suex"
which stands for **Su**per **Ex**tractor script.

## Usage
This script is primarily intended to be run from cron, so the idea is to
edit the two config files (suex_config.json and suex_subs.json), then add
"suex.py -a" to your crontab.

There are some command line options available which are described by the
-h option.

```
usage: suex.py [-h] (-a | -r RECIPIENT | -x EXTRACT) [-m MESSAGE] [-v]

optional arguments:
  -h, --help            show this help message and exit
  -a, --all             run extractor on all configured entries
  -r RECIPIENT, --recipient RECIPIENT
                        run extractor for specified subscriber
  -x EXTRACT, --extract EXTRACT
                        extract specific entry to stdout (for testing
                        extractor)
  -m MESSAGE, --message MESSAGE
                        add custom message to email
  -v, --version         show program's version number and exit
```

For example, to test the deBono extractor and have the script print the
extracted content, run "suex.py -x deBono".

## suex_config.json file format

TODO

### How to define an extractor

TODO

## suex_subs.json file format

TODO
