Test ARI
========

Environment
-----------
* Python 3.5.2
* Asterisk 16.20
* Ubuntu 16.04 LTS

Installation
------------

`pip3 install -r requirements.txt`

Configuration
-------------
`configs/asterisk.ini` configs for http connection to asterisk

`configs/calls.ini` call settings

Call settings
-------------
* `count` is simultaneous calls count
* `driver` is channel driver (SIP/PJSIP)
* `phone` is called phone number
* `callerid` is callerid for this call
* `trunk` is SIP trunk to call

Usage
-----
`python3 call_sender.py`
