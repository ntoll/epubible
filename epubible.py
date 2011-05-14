#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A simple script to create a customised EPUB version of the Bible from data
stored in Fluidinfo.

(c) 2011 Fluidinfo Inc.

Author: Nicholas Tollervey (ntoll <at> fluidinfo.com)
"""
import fluidinfo
import logging
import os
import httplib2
from shutil import copyfile
from jinja2 import Environment, FileSystemLoader
from getpass import getpass
from datetime import date
from uuid import uuid4


# set up the logger
logger = logging.getLogger("epubible")
logger.setLevel(logging.DEBUG)
logfile_handler = logging.FileHandler('epubible.log')
logfile_handler.setLevel(logging.DEBUG)
log_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - "\
                               "%(message)s")
logfile_handler.setFormatter(log_format)
logger.addHandler(logfile_handler)


def grabCredentials():
    """
    Grabs user's Fluidinfo credentials and makes sure the Authorization headers
    are set.
    """
    print "Please enter your Fluidinfo username and password:"
    username = raw_input("Username: ")
    password = getpass("Password: ")
    logger.info("Logging in as %s" % username)
    fluidinfo.login(username, password)
    return username


def createHasRead(username):
    """
    Asks for confirmation to create the 'has-read' tag under the user's root
    namespace.
    """
    logger.info("Processing has-read tag")
    confirmation = raw_input("Create 'has-read' tag..? [y/n]").lower()
    if confirmation == 'y':
        path = '/tags/%s' % username
        payload = {'name': 'has-read', 'description':
            'Indicates the referenced object has been read by the user on a'\
            ' particular date (stored as a string representation of ISO date).',
            'indexed': False}
        logger.info(fluidinfo.call('POST', path, payload))
    else:
        logger.info("Has-read tag ignored/declined")


def getTagsToSelect():
    """
    Returns a list of tags that the user wants returning whose values will be
    used to build the customised version of the Bible.
    """
    logger.info('Getting tags to return')
    while True:
        raw_tags = raw_input("Comma separated list of tags to retrieve: ")
        tags = [t.strip() for t in raw_tags.split(',')]
        if tags:
            break;
        else:
            print "Please try again..."
    # We always want to have the fluiddb/about tag value returned
    required_tags = ['fluiddb/about', 'kingjamesbible/book',
        'kingjamesbible/chapter', 'kingjamesbible/verse']
    for required in required_tags:
        if not required in tags:
            tags.append(required)
    logger.info(tags)
    return tags


def getQuery():
    """
    Returns the Query to use to select objects of interest from Fluidinfo
    """
    logger.info('Getting query')
    query = raw_input("Query: ")
    # Perhaps do some calidation here..?
    logger.info(query)
    return query


def getResultsFromFluidinfo(tags, query):
    """
    Does exactly what it says on the tin... :-)
    """
    logger.info('Fetching results from Fluidinfo')
    print "Fetching result from Fluidinfo..."
    headers, results = fluidinfo.call('GET', '/values', tags=tags, query=query)
    logger.info(headers)
    if headers['status'] == '200':
        print 'OK'
        return results
    else:
        print 'There was a problem getting your results. Check the log!'
        logger.warning('Problem getting results. Check the headers above.')
        return {}


def markAsRead(username, query):
    """
    Attempts to mark the appropriate objects as read on the current date. Will
    log any failures but won't report them via the command line.
    """
    payload = {'%s/has-read' % username:
        {'value': '%s' % date.today().isoformat()}}
    logger.info('Updating objects with query: %s' % query)
    logger.info('Updating objects with payload: %r' % payload)
    logger.info(fluidinfo.call('PUT', '/values', payload, query=query))


def getVerses(raw_results):
    """
    Given some raw JSON from Fluidinfo will return an ordered list of the
    verses represented as dictionaries.
    """
    logger.info('Cleaning results')
    clean_results = []
    for obj in raw_results['results']['id'].values():
        clean_obj = {}
        for k, v in obj.iteritems():
            if 'value' in v:
                clean_obj[k] = v['value']
            elif 'value-type' in v:
                # check for a reference to an image
                if 'image' in v['value-type']:
                    path = 'https://fluiddb.fluidinfo.com/about/%s/%s'
                    clean_object['k'] = path % (obj['fluiddb/about']['value'],
                        k)
                else:
                    # ignore other opaque types
                    pass
        clean_results.append(clean_obj)
    logger.info('Cleaned %d results' % len(clean_results))
    return clean_results


def compareVerses(x, y):
    """
    Given two verses will return an indication of order by comparison
    """
    if x['kingjamesbible/chapter'] == y['kingjamesbible/chapter']:
        return cmp(x['kingjamesbible/verse'], y['kingjamesbible/verse'])
    else:
        return cmp(x['kingjamesbible/chapter'], y['kingjamesbible/chapter'])

def orderResults(raw_results):
    """
    Given an unordered list of results places them in the correct order.

    Currently this is very naively done. However it'll change to be the right
    order for the bible in future iterations.
    """
    logger.info('Ordering results by about tag value.')
    raw_results.sort(cmp=compareVerses)
    return raw_results


def isValidImage(url):
    """
    A simple heuristic to check if the resource at the end of the URL is an
    image appropriate to be embedded in a EPUB.
    """
    logger.info('Checking url as image: %s' % url)
    image_extensions = ['.jpg', '.png', '.gif', '.svg']
    for i in image_extensions:
        if url.endswith(i):
            return True
    return False


def getImageFilename(url):
    """
    Returns the filename at the end of the URL that references an image.
    """
    head, filename = url.rsplit('/', 1)
    return filename


def getImages(results, directory):
    """
    Given the results set will grab the images from the Internet that are
    referenced therein.
    """
    logger.info('Getting images.')
    image_set = set()
    for r in results:
        bad_urls = []
        for k, v in r.iteritems():
            if type(v) is list:
                for image in v:
                    if image.startswith('http'):
                        if isValidImage(image):
                            image_set.add(image)
                        else:
                            bad_urls.append(k)
        for k in bad_urls:
            del(r[k])
    logger.info('Found the following images: %s' % image_set)
    image_filenames = []
    for img in image_set:
        logger.info('Getting image from %s' % img)
        http = httplib2.Http()
        headers, content = http.request(img, 'GET')
        logger.info(headers)
        image_name = getImageFilename(img)
        output = open(os.path.join(directory, 'OEBPS', 'images', image_name),
            'wb')
        output.write(content)
        output.close()
        n, mime = image_name.rsplit('.' ,1)
        i = { 'filename': image_name,
              'id': image_name,
              'mime': 'image/%s' % mime}
        image_filenames.append(i)
    logger.info('Downloaded %d images' % len(image_filenames))
    return image_filenames


def getItems(results):
    """
    Returns an ordered list of objects each of which has a render method to
    generate the appropriate output.
    """
    rendered = []
    rendered_images = set()
    chapter = 0
    for item in results:
        b, c, v= item['fluiddb/about'].split(':')
        c = int(c)
        r = ""
        if c > chapter:
            chapter = c
            r+="<br/><br/>"
        for k, v in item.iteritems():
            if type(v) is list:
                for i in v:
                    if i.startswith('http'):
                        # it has an image
                        if not i in rendered_images:
                            rendered_images.add(i)
                            r+='''<div>
<img src="images/%s" alt="An illustration"/>
</div>''' % getImageFilename(i)
                rendered.append(r)
            elif 'text' in k:
                r+="%s" % v.replace('&nbsp;', '')
                rendered.append(r)
    return rendered


def createEpubDirectory(directory, username, results):
    """
    Use templates to create a temporary directory of the EPUB content
    """
    logger.info('Creating EPUB in temporary directory %s' % directory)
    os.mkdir(directory)
    # Create the directory structure
    template_directories = []
    for templates in os.walk('templates'):
        template_directories.append(templates[0])
        root = templates[0].replace('templates', directory)
        for child_directory in templates[1]:
            os.mkdir(os.path.join(root, child_directory))
    env = Environment(loader=FileSystemLoader(template_directories))
    context = {
        'title': 'The Bible',
        'uuid': str(uuid4()),
        'name': username,
        'date': date.today().isoformat(),
        'images': getImages(results, directory),
        'items': getItems(results)
    }
    # Copy over and render the files via Jinja2
    for templates in os.walk('templates'):
        root = templates[0].replace('templates', directory)
        for template_file in templates[2]:
            logger.info('Processing template %s' % template_file)
            # use these as templates to be save to the appropriate location
            # in the temporary directory
            if template_file.endswith('.png'):
                # just copy over the cover
                src = os.path.join(templates[0], template_file)
                dest = os.path.join(root, template_file)
                copyfile(src, dest)
            else:
                template = env.get_template(template_file)
                rendered = template.render(context)
                output = open(os.path.join(root, template_file), 'w')
                output.write(rendered)
                output.close()


def zipEpubDirectory(directory):
    """
    Given a temporary directory containing the files for an EPUB book, this
    method zips it up correctly.
    """
    logger.info('Zipping up EPUB')
    os.chdir(directory)
    os.system("zip -0Xq bible.epub mimetype")
    os.system("zip -Xr9Dq bible.epub *")
    os.system("cp bible.epub ..")

# Validate

# Upload to Fluidinfo..?

if __name__ == '__main__':
    username = grabCredentials()
    createHasRead(username)
    tags = getTagsToSelect()
    query = getQuery()
    results = getResultsFromFluidinfo(tags, query)
    markAsRead(username, query)
    clean_verses = getVerses(results)
    orderResults(clean_verses)
    directory = 'tempBible'
    cwd = os.getcwd()
    try:
        createEpubDirectory(directory, username, clean_verses)
        zipEpubDirectory(directory)
    finally:
        # remove the directory
        os.chdir(cwd)
        os.system("rm -rf %s" % directory)

