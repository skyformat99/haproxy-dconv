#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2012 Cyril Bonté
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''
TODO : ability to split chapters into several files
TODO : manage keyword locality (server/proxy/global ; ex : maxconn)
TODO : Remove global variables where possible
'''
import os, subprocess, sys, cgi, re
import time
import datetime

from optparse import OptionParser
from mako.template import Template

VERSION = ""
DATE = ""
HAPROXY_GIT_VERSION = False

def main():
    global VERSION, DATE, HAPROXY_GIT_VERSION

    VERSION = get_git_version()
    DATE = get_git_date()
    if not VERSION or not DATE:
        sys.exit(1)

    usage="Usage: %prog --infile <infile> --outfile <outfile>"

    parser = OptionParser(description='Generate HTML Document from HAProxy configuation.txt',
                          version=VERSION,
                          usage=usage)
    parser.add_option('--infile', '-i', help='Input file mostly the configuration.txt')
    parser.add_option('--outfile','-o', help='Output file')
    (option, args) = parser.parse_args()

    if not (option.infile  and option.outfile) or len(args) > 0:
        parser.print_help()
        exit(1)

    HAPROXY_GIT_VERSION = get_haproxy_git_version(os.path.dirname(option.infile))

    convert(option.infile, option.outfile)


# Temporarily determine the version from git to follow which commit generated
# the documentation
def get_git_version():
    if not os.path.isdir(".git"):
        print >> sys.stderr, "This does not appear to be a Git repository."
        return
    try:
        p = subprocess.Popen(["git", "describe", "--tags", "--match", "v*"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except EnvironmentError:
        print >> sys.stderr, "Unable to run git"
        return
    version = p.communicate()[0]
    if p.returncode != 0:
        print >> sys.stderr, "Unable to run git"
        return

    if len(version) < 2:
        return

    version = version[1:].strip()
    return version

# Temporarily determine the last commit date from git
def get_git_date():
    if not os.path.isdir(".git"):
        print >> sys.stderr, "This does not appear to be a Git repository."
        return
    try:
        p = subprocess.Popen(["git", "log", "-1", '--format=%ct'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except EnvironmentError:
        print >> sys.stderr, "Unable to run git"
        return
    date = p.communicate()[0]
    if p.returncode != 0:
        print >> sys.stderr, "Unable to run git"
        return

    return date

def get_haproxy_git_version(path):
    try:
        p = subprocess.Popen(["git", "describe", "--tags", "--match", "v*"], cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except EnvironmentError:
        return False
    version = p.communicate()[0]

    if p.returncode != 0:
        return False

    if len(version) < 2:
        return False

    version = version[1:].strip()
    version = re.sub(r'-g.*', '', version)
    return version

def getTitleDetails(string):
    array = string.split(".")

    title    = array.pop().strip()
    chapter  = ".".join(array)
    level    = max(1, len(array))
    if array:
        toplevel = array[0]
    else:
        toplevel = False

    return {
            "title"   : title,
            "chapter" : chapter,
            "level"   : level,
            "toplevel": toplevel
    }

# Parse the wole document to insert links on keywords
def createLinks():
    global document, keywords, keywordsCount, keyword_conflicts, chapters

    print >> sys.stderr, "Generating keywords links..."

    for keyword in keywords:
        keywordsCount[keyword] = document.count('&quot;' + keyword + '&quot;')
        if (keyword in keyword_conflicts) and (not keywordsCount[keyword]):
            # The keyword is never used, we can remove it from the conflicts list
            del keyword_conflicts[keyword]

        if keyword in keyword_conflicts:
            chapter_list = ""
            for chapter in keyword_conflicts[keyword]:
                chapter_list += '<li><a href="#%s (%s)">%s</a></li>' % (keyword, chapters[chapter]['title'], chapters[chapter]['title'])
            document = document.replace('&quot;' + keyword + '&quot;',
                    '&quot;<span class="dropdown">' +
                    '<a class="dropdown-toggle" data-toggle="dropdown" href="#">' +
                    keyword +
                    '<span class="caret"></span>' +
                    '</a>' +
                    '<ul class="dropdown-menu">' +
                    '<div>This keyword is available in sections :</div>' +
                    chapter_list +
                    '</ul>' +
                    '</span>&quot;')
        else:
            document = document.replace('&quot;' + keyword + '&quot;', '&quot;<a href="#' + keyword + '">' + keyword + '</a>&quot;')
        if keyword.startswith("option "):
            shortKeyword = keyword[len("option "):]
            keywordsCount[shortKeyword] = document.count('&quot;' + shortKeyword + '&quot;')
            if (shortKeyword in keyword_conflicts) and (not keywordsCount[shortKeyword]):
            # The keyword is never used, we can remove it from the conflicts list
                del keyword_conflicts[shortKeyword]
            document = document.replace('&quot;' + shortKeyword + '&quot;', '&quot;<a href="#' + keyword + '">' + shortKeyword + '</a>&quot;')

def documentAppend(text, retline = True):
    global document
    document += text
    if retline:
        document += "\n"

# Render tables detected by the conversion parser
def renderTable(table, maxColumns = 0, hasKeywords = False):
    title = None
    if isinstance(table, dict):
        title = table["title"]
        table = table["rows"]

    if not maxColumns:
        maxColumns = len(table[0])

    if title:
        documentAppend('<p>%s :' % title, False)

    documentAppend('<table class=\"table table-bordered\" border="0" cellspacing="0" cellpadding="0">', False)
    mode = "th"
    headerLine = ""
    i = 0
    for row in table:
        line = ""

        if i == 0:
            line += '<thead>'
        elif i > 1 and (i  - 1) % 20 == 0:
            # Repeat headers periodically for long tables
            line += headerLine

        line += '<tr>'

        j = 0
        for column in row:
            if j >= maxColumns:
                break
            data = column.strip()
            if data in ['yes']:
                open = '<%s class="alert-success"><div class="pagination-centered">' % mode
                close = '</div></%s>' % mode
            elif data in ['no']:
                open = '<%s class="alert-error"><div class="pagination-centered">' % mode
                close = '</div></%s>' % mode
            elif data in ['X', '-']:
                open = '<%s><div class="pagination-centered">' % mode
                close = '</div></%s>' % mode
            else:
                open = '<%s>' % mode
                close = '</%s>' % mode
            keyword = column
            if j == 0 and i != 0 and hasKeywords:
                if keyword.startswith("[no] "):
                    keyword = keyword[len("[no] "):]
                open += '<a href="#%s-%s">' % (hasKeywords, keyword)
                close = '</a>' + close
            if j == 0 and len(row) > maxColumns:
                for k in xrange(maxColumns, len(row)):
                    open = open + '<span class="pull-right">' + row[k] + '</span>'
            line += '%s%s%s' % (open, data, close)
            j += 1
        mode = "td"
        line += '</tr>'

        if i == 0:
            line += '</thead>'
            headerLine = line

        documentAppend(line, False)

        i += 1
    documentAppend('</table>', False)

    if title:
        documentAppend('</p>', False)

# Used to colorize keywords parameters
# TODO : use CSS styling
def colorize(text):
    colorized = ""
    tags = [
            [ "["   , "]"   , "#008" ],
            [ "{"   , "}"   , "#800" ],
            [ "&lt;", "&gt;", "#080" ],
    ]
    heap = []
    pos = 0
    while pos < len(text):
        substring = text[pos:]
        found = False
        for tag in tags:
            if substring.startswith(tag[0]):
                # Opening tag
                heap.append(tag)
                colorized += '<span style="color: %s">%s' % (tag[2], substring[0:len(tag[0])])
                pos += len(tag[0])
                found = True
                break
            elif substring.startswith(tag[1]):
                # Closing tag

                # pop opening tags until the corresponding one is found
                openingTag = False
                while heap and openingTag != tag:
                    openingTag = heap.pop()
                    if openingTag != tag:
                        colorized += '</span>'
                # all intermediate tags are now closed, we can display the tag
                colorized += substring[0:len(tag[1])]
                # and the close it if it was previously opened
                if openingTag == tag:
                    colorized += '</span>'
                pos += len(tag[1])
                found = True
                break
        if not found:
            colorized += substring[0]
            pos += 1
    # close all unterminated tags
    while heap:
        tag = heap.pop()
        colorized += '</span>'

    return colorized

def get_indent(line):
    i = 0
    length = len(line)
    while i < length and line[i] == ' ':
        i += 1
    return i

# The parser itself
# TODO : simplify the parser ! Make it clearer and modular.
def convert(infile, outfile):
    global document, keywords, keywordsCount, chapters, keyword_conflicts

    data = []
    fd = file(infile,"r")
    for line in fd:
        line.replace("\t", " " * 8)
        line = line.rstrip()
        data.append(line)
    fd.close()

    context = {
            'headers':      {},
            'document':     ""
    }

    sections = []
    currentSection = {
            "details": getTitleDetails(""),
            "content": "",
    }

    chapters = {}

    keywords = {}
    keywordsCount = {}

    specialSections = {
            "default": {
                    "hasKeywords": True,
            },
            "4.1": {
                    "hasKeywords": True,
            },
    }

    print >> sys.stderr, "Importing %s..." % infile

    nblines = len(data)
    i = j = 0
    while i < nblines:
        line = data[i].rstrip()
        if i < nblines - 1:
            next = data[i + 1].rstrip()
        else:
            next = ""
        if (line == "Summary" or re.match("^[0-9].*", line)) and (len(next) > 0) and (next[0] == '-') and ("-" * len(line) == next):
            sections.append(currentSection)
            currentSection = {
                    "details": getTitleDetails(line),
                    "content": "",
            }
            j = 0
            i += 1 # Skip underline
            while not data[i + 1].rstrip():
                i += 1 # Skip empty lines

        else:
            if len(line) > 80:
                print >> sys.stderr, "Line `%i' exceeds 80 columns" % (i + 1)

            currentSection["content"] = currentSection["content"] + line + "\n"
            j += 1
            if currentSection["details"]["title"] == "Summary" and line != "":
                # Learn chapters from the summary
                details = getTitleDetails(line)
                if details["chapter"]:
                    chapters[details["chapter"]] = details
        i += 1
    sections.append(currentSection)

    chapterIndexes = sorted(chapters.keys())

    document = ""
    for section in sections:
        details = section["details"]
        level = details["level"]
        title = details["title"]
        content = section["content"].rstrip()

        print >> sys.stderr, "Parsing chapter %s..." % title

        if title == "Summary":
            continue

        if title:
            fulltitle = title
            if details["chapter"]:
                documentAppend("<a name=\"%s\"></a>" % details["chapter"])
                fulltitle = details["chapter"] + ". " + title
                if not details["chapter"] in chapters:
                    print >> sys.stderr, "Adding '%s' to the summary" % details["title"]
                    chapters[details["chapter"]] = details
                    chapterIndexes = sorted(chapters.keys())
            if level == 1:
                documentAppend("<div class=\"page-header\">", False)
            documentAppend("<h%d><small>%s.</small> %s</h%d>" % (level, details["chapter"], cgi.escape(title, True), level))
            if level == 1:
                documentAppend("</div>", False)

        if content:
            if False and title:
                # Display a navigation bar
                documentAppend('<ul class="well pager">')
                documentAppend('<li><a href="#top">Top</a></li>', False)
                index = chapterIndexes.index(details["chapter"])
                if index > 0:
                    documentAppend('<li class="previous"><a href="#%s">Previous</a></li>' % chapterIndexes[index - 1], False)
                if index < len(chapterIndexes) - 1:
                    documentAppend('<li class="next"><a href="#%s">Next</a></li>' % chapterIndexes[index + 1], False)
                documentAppend('</ul>', False)
            content = cgi.escape(content, True)
            content = re.sub(r'section ([0-9]+(.[0-9]+)*)', r'<a href="#\1">section \1</a>', content)

            #keywordPattern = re.compile(r'^((([a-z0-9\-_\.\(\)]|&lt;|&gt;)+[a-z0-9\)])( +[a-z0-9][a-z0-9\-_\.\(\)]*[a-z0-9\)])*)(.*)')
            #keywordPattern = re.compile('^(((\(&lt;[a-z0-9\-_\.]+&lt;\))? +[a-z0-9][a-z0-9\-_\.\(\)]*[a-z0-9\)])*)(.*)')
            keywordPattern = re.compile(r'^(%s%s)(%s)' % (
                    '([a-z][a-z0-9\-_\.]*[a-z0-9\-_)])',    # keyword
                    '( [a-z0-9\-_]+)*',             # subkeywords
                    '(\(&lt;[a-z0-9]+&gt;\))?'      # arg
                    ))
            tablePattern = re.compile(r'^ *(-+\+)+-+')

            lines = content.split("\n")
            nblines = len(lines)
            i = 0

            if not title:
                context['headers'] = {
                        'title':        lines[1].strip(),
                        'subtitle':     lines[2].strip(),
                        'version':      lines[4].strip(),
                        'author':       lines[5].strip(),
                        'date':         lines[6].strip()
                }
                if HAPROXY_GIT_VERSION:
                    context['headers']['version'] = 'version ' + HAPROXY_GIT_VERSION

                # Skip header lines
                while lines[i]:
                    i += 1
                while not lines[i]:
                    i += 1

            documentAppend('<pre>', False)

            while i < nblines:
                try:
                    specialSection = specialSections[details["chapter"]]
                except:
                    specialSection = specialSections["default"]

                line = lines[i]
                if i < nblines - 1:
                    nextline = lines[i + 1]
                else:
                    nextline = ""

                line = re.sub(r'(Arguments :)', r'<span class="label label-info">\1</span>', line)
                line = re.sub(r'(See also *:)', r'<span class="label label-see-also">\1</span>', line)

                if re.match(r'^ *Examples? *:$', line):
                    # Detect examples blocks
                    line = re.sub(r'(Examples? *:)', r'<span class="label label-success">\1</span>', line)
                    documentAppend(line)
                    indent = get_indent(line)
                    i +=1
                    while not lines[i]:
                        i += 1 # Skip empty lines

                    if get_indent(lines[i]) > indent:
                        documentAppend("<pre>", False)
                        add_empty_line = 0
                        while i < len(lines) and ((not lines[i]) or (get_indent(lines[i]) > indent)):
                            if lines[i]:
                                for j in xrange(0, add_empty_line):
                                    documentAppend("")
                                documentAppend(lines[i])
                                add_empty_line = 0
                            else:
                                add_empty_line += 1
                            i += 1
                        documentAppend("</pre>")
                    continue

                # Some examples are currently too complex to parse, well, just colorize the header for now.
                # See below : a description on the same line as the label 'Example:' but continues on several lines
                # Example: accept all connections from white-listed hosts, count all other
                #          connections and reject too fast ones. This results in abusive ones
                #          being blocked as long as they don't slow down.
                line = re.sub(r'(Examples? *:)', r'<span class="label label-success">\1</span>', line)

                if context['headers']['subtitle'] == 'Configuration Manual' and tablePattern.match(nextline):
                    # activate table rendering only for th Configuration Manual
                    lineSeparator = nextline
                    nbColumns = nextline.count("+") + 1
                    extraColumns = 0
                    print >> sys.stderr, "Entering table mode (%d columns)" % nbColumns
                    table = []
                    if line.find("|") != -1:
                        row = []
                        while i < nblines:
                            line = lines[i]
                            if i < nblines - 1:
                                nextline = lines[i + 1]
                            else:
                                nextline = ""
                            if line == lineSeparator:
                                # New row
                                table.append(row)
                                row = []
                                if nextline.find("|") == -1:
                                    break # End of table
                            else:
                                # Data
                                columns = line.split("|")
                                for j in xrange(0, len(columns)):
                                    try:
                                        if row[j]:
                                            row[j] += "<br />"
                                        row[j] += columns[j].strip()
                                    except:
                                        row.append(columns[j].strip())
                            i = i + 1
                    else:
                        row = []
                        headers = nextline
                        while i < nblines:
                            line = lines[i]
                            if i < nblines - 1:
                                nextline = lines[i + 1]
                            else:
                                nextline = ""

                            if nextline == "":
                                if row: table.append(row)
                                break # End of table

                            if (line != lineSeparator) and (line[0] != "-"):
                                start = 0

                                if row and not line.startswith(" "):
                                    # Row is complete, parse a new one
                                    table.append(row)
                                    row = []

                                tmprow = []
                                while start != -1:
                                    end = headers.find("+", start)
                                    if end == -1:
                                        end = len(headers)

                                    realend = end
                                    if realend == len(headers):
                                        realend = len(line)
                                    else:
                                        while realend < len(line) and line[realend] != " ":
                                            realend += 1
                                            end += 1

                                    tmprow.append(line[start:realend])

                                    start = end + 1
                                    if start >= len(headers):
                                        start = -1
                                for j in xrange(0, nbColumns):
                                    try:
                                        row[j] += tmprow[j].strip()
                                    except:
                                        row.append(tmprow[j].strip())

                                deprecated = row[0].endswith("(deprecated)")
                                if deprecated:
                                    row[0] = row[0][: -len("(deprecated)")].rstrip()

                                nooption = row[1].startswith("(*)")
                                if nooption:
                                    row[1] = row[1][len("(*)"):].strip()

                                if deprecated or nooption:
                                    extraColumns = 1
                                    extra = ""
                                    if deprecated:
                                        extra += '<span class="label label-warning">(deprecated)</span>'
                                    if nooption:
                                        extra += '<span>(*)</span>'
                                    row.append(extra)

                            i += 1
                    print >> sys.stderr, "Leaving table mode"
                    renderTable(table, nbColumns, details["toplevel"])
                    i += 1 # skip useless next line
                    continue
                elif line.find("May be used in sections") != -1:
                    rows = []
                    headers = line.split(":")
                    rows.append(headers[1].split("|"))
                    rows.append(nextline.split("|"))
                    table = {
                            "rows": rows,
                            "title": headers[0]
                    }
                    renderTable(table)
                    i += 2 # skip this previous table
                    continue


                if (len(line) > 0) and (len(nextline) > 0) and (nextline[0] == '-') and ("-" * len(line) == nextline):
                        # Detect underlines
                    documentAppend('<h5>%s</h5>' % line, False)
                    i += 1 # Skip underline
                    while not lines[i + 1].rstrip():
                        i += 1 # Skip empty lines
                elif line != "" and not re.match(r'^ ', line):
                    parsed = keywordPattern.match(line)
                    if parsed != None:

                        keyword = parsed.group(1)
                        arg     = parsed.group(4)
                        parameters = line[len(keyword) + len(arg):]
                        if parameters != "" and not re.match("^ +(&lt;|\[|\{|/|\(deprecated\))", parameters):
                            keyword = False
                        else:
                            splitKeyword = keyword.split(" ")
                        parameters = arg + parameters
                    else:
                        keyword = False

                    if keyword and (len(splitKeyword) <= 5):
                        toplevel = details["toplevel"]
                        for j in xrange(0, len(splitKeyword)):
                            subKeyword = " ".join(splitKeyword[0:j + 1])
                            if subKeyword != "no":
                                if not subKeyword in keywords:
                                    keywords[subKeyword] = set()
                                keywords[subKeyword].add(toplevel)
                            documentAppend('<a name="%s"></a>' % subKeyword, False)
                            documentAppend('<a name="%s-%s"></a>' % (toplevel, subKeyword), False)
                            documentAppend('<a name="%s-%s"></a>' % (details["chapter"], subKeyword), False)
                            documentAppend('<a name="%s (%s)"></a>' % (subKeyword, chapters[toplevel]['title']), False)
                            documentAppend('<a name="%s (%s)"></a>' % (subKeyword, chapters[details["chapter"]]['title']), False)

                        deprecated = parameters.find("(deprecated)")
                        if deprecated != -1:
                            prefix = ""
                            suffix = ""
                            parameters = parameters.replace("(deprecated)", '<span class="label label-warning">(deprecated)</span>')
                        else:
                            prefix = ""
                            suffix = ""

                        while nextline.startswith("   "):
                            # Found parameters on the next line
                            parameters += "\n" + nextline
                            i += 1
                            if i < nblines - 1:
                                nextline = lines[i + 1]
                            else:
                                nextline = ""


                        parameters = colorize(parameters)

                        documentAppend('<div class="keyword">%s<b><a name="%s"></a><a href="#%s-%s">%s</a></b>%s%s</div>' % (prefix, keyword, toplevel, keyword, keyword, parameters, suffix), False)
                    elif line.startswith("/*"):
                        # Skip comments in the documentation
                        while not lines[i].endswith("*/"):
                            i += 1
                    else:
                        # This is probably not a keyword but a text, ignore it
                        documentAppend(line)
                else:
                    documentAppend(line)
                i = i + 1
            documentAppend('</pre><br />')

    # Log warnings for keywords defined in several chapters
    keyword_conflicts = {}
    for keyword in keywords:
        keyword_chapters = list(keywords[keyword])
        keyword_chapters.sort()
        if len(keyword_chapters) > 1:
            print >> sys.stderr, 'Multi section keyword : "%s" in chapters %s' % (keyword, list(keyword_chapters))
            keyword_conflicts[keyword] = keyword_chapters

    keywords = list(keywords)
    keywords.sort()

    createLinks()

    # Add the keywords conflicts to the keywords list to make them available in the search form
    # And remove the original keyword which is now useless
    for keyword in keyword_conflicts:
        sections = keyword_conflicts[keyword]
        offset = keywords.index(keyword)
        for section in sections:
            keywords.insert(offset, "%s (%s)" % (keyword, chapters[section]['title']))
            offset += 1
        keywords.remove(keyword)

    print >> sys.stderr, "Exporting to %s..." % outfile

    template = Template(filename=os.path.join(os.path.dirname(__file__), 'templates', 'template.html'))

    fd = open(outfile,'w')

    print >> fd, template.render(
            headers = context['headers'],
            document = document,
            chapters = chapters,
            chapterIndexes = chapterIndexes,
            keywords = keywords,
            keywordsCount = keywordsCount,
            keyword_conflicts = keyword_conflicts,
            version = VERSION,
            date = datetime.datetime.fromtimestamp(int(DATE)).strftime("%Y/%m/%d")
    )
    fd.close()

if __name__ == '__main__':
    main()
