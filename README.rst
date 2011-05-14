epubible
========

A script to create a customised EPUB of the Bible from data stored in Fluidinfo.

Requires the fluidinfo.py module installed (pip install -U fluidinfo.py).

To use it simply run from the command line. Here's an example session::

    $ ./epubible.py
    Please enter your Fluidinfo username and password:
    Username: ntoll
    Password: *********
    Create 'has-read' tag..? [y/n]
    Comma separated list of tags to retrieve: lolcat/bible/text, bricktestament/images
    Query: kingjamesbible/book = "1 John"
    Fetching result from Fluidinfo...
    OK

The session above gets the text from the lolcat version of the bible and illustrations from the bricktestament for all objects that are in tagged as being in the book "1 John" in the King James version of the Bible.

The result is a new file in the local directory called "bible.epub". Try it :-)

Nota Bene: This is a buggy quick hack. Needs tests and lots of love... especially on the epub side of things.
