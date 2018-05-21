#!/usr/bin/env python

'''A tiny library for parsing, modifying, and composing SRT files.'''

from __future__ import unicode_literals
import functools
import re
from datetime import timedelta
import logging
import pprint


log = logging.getLogger(__name__)

# "." is not technically valid as a delimiter, but many editors create SRT
# files with this delimiter for whatever reason. Many editors and players
# accept it, so we do too.
RGX_TIMESTAMP_MAGNITUDE_DELIM = r'[,.:]'
RGX_TIMESTAMP = RGX_TIMESTAMP_MAGNITUDE_DELIM.join([r'\d+'] * 4)
RGX_INDEX = r'\d+'
RGX_PROPRIETARY = r'[^\r\n]*'
RGX_CONTENT = r'.*?'
RGX_POSSIBLE_CRLF = r'\r?\n'

SRT_REGEX = re.compile(
    r'({idx})\s*{eof}({ts}) --> ({ts}) ?({proprietary}){eof}({content})'
    # Many sub editors don't add a blank line to the end, and many editors and
    # players accept that. We allow it to be missing in input.
    #
    # We also allow subs that are missing a double blank newline. This often
    # happens on subs which were first created as a mixed language subtitle,
    # for example chs/eng, and then were stripped using naive methods (such as
    # ed/sed) that don't understand newline preservation rules in SRT files.
    #
    # This means that when you are, say, only keeping chs, and the line only
    # contains english, you end up with not only no content, but also all of
    # the content lines are stripped instead of retaining a newline.
    r'(?:{eof}|\Z)(?:{eof}|\Z|(?=(?:{idx}\s*{eof}{ts})))'
    # Some SRT blocks, while this is technically invalid, have blank lines
    # inside the subtitle content. We look ahead a little to check that the
    # next lines look like an index and a timestamp as a best-effort
    # solution to work around these.
    r'(?=(?:{idx}\s*{eof}{ts}|\Z))'.format(
        idx=RGX_INDEX,
        ts=RGX_TIMESTAMP,
        proprietary=RGX_PROPRIETARY,
        content=RGX_CONTENT,
        eof=RGX_POSSIBLE_CRLF,
    ),
    re.DOTALL,
)
TS_LEN = 12
STANDARD_TS_COLON_OFFSET = 2

ZERO_TIMEDELTA = timedelta(0)

# Warning message if truthy return -> Function taking a Subtitle, skip if True
SUBTITLE_SKIP_CONDITIONS = (
    ('No content', lambda sub: not sub.content.strip()),
    ('Start time < 0 seconds', lambda sub: sub.start_ts_ < ZERO_TIMEDELTA),
    ('Subtitle start time >= end time', lambda sub: sub.start_ts_ >= sub.end_ts_),
)

SECONDS_IN_HOUR = 3600
SECONDS_IN_MINUTE = 60
HOURS_IN_DAY = 24
MICROSECONDS_IN_MILLISECOND = 1000

@functools.total_ordering
class Subtitle(object):
    r'''
    The metadata relating to a single subtitle. Subtitles are sorted by start
    time by default.

    :param int index: The SRT index for this subtitle
    :param start: The time that the subtitle should start being shown
    :type start: :py:class:`datetime.timedelta`
    :param end: The time that the subtitle should stop being shown
    :type end: :py:class:`datetime.timedelta`
    :param str proprietary: Proprietary metadata for this subtitle
    :param str content: The subtitle content
    '''

    def __init__(self, index, content, start=None, start_timedelta=None, end=None, end_timedelta=None, proprietary=None):
        '''
        srt timestamp : '%02d:%02d:%02d, %03d'
        timedelta : datetime.timedelta(0, 4984)
        '''
        self.index_ = index
        self.start_ts_ = start
        self.start_timedelta_ = start_timedelta
        self.end_ts_ = end
        self.end_timedelta_ = end_timedelta
        self.contents_ = content
        self.proprietary = proprietary

    def __hash__(self):
        return hash(frozenset(vars(self).items()))

    def __eq__(self, other):
        return vars(self) == vars(other)

    def __lt__(self, other):
        return self.start_ts_ < other.start_ts_ or (
            self.start_ts_ == other.start_ts_ and self.end_ts_ < other.end_ts_
        )

    def __repr__(self):
        # Python 2/3 cross compatibility
        var_items = getattr(
            vars(self), 'iteritems', getattr(vars(self), 'items')
        )
        item_list = ', '.join(
            '%s=%r' % (k, v) for k, v in var_items()
        )
        return "%s(%s)" % (type(self).__name__, item_list)

    def to_srt(self, strict=True, eol=None):
        r'''
        Convert the current :py:class:`Subtitle` to an SRT block.

        :param bool strict: If disabled, will allow blank lines in the content
                            of the SRT block, which is a violation of the SRT
                            standard and may case your media player to explode
        :param str eol: The end of line string to use (default "\n")
        :returns: The metadata of the current :py:class:`Subtitle` object as an
                  SRT formatted subtitle block
        :rtype: str
        '''
        output_content = self.content
        output_proprietary = self.proprietary

        if output_proprietary:
            # output_proprietary is output directly next to the timestamp, so
            # we need to add the space as a field delimiter.
            output_proprietary = ' ' + output_proprietary

        if strict:
            output_content = make_legal_content(output_content)

        if eol is not None:
            output_content = output_content.replace('\n', eol)
        else:
            eol = '\n'

        template = '{idx}{eol}{start} --> {end}{prop}{eol}{contents}{eol}{eol}'
        return template.format(
            idx=self.index_, 
            start=timedelta_to_srt_timestamp(self.start_ts_),
            end=timedelta_to_srt_timestamp(self.end_ts_), 
            prop=output_proprietary,
            contents=output_content, 
            eol=eol,
        )

def make_a_subtitle(_index, _start_ts, _contents, _end_ts, _prop=None, _strict=None, _eol=None):
    return Subtitle( 
        _index, 
        _contents, 
        _start_ts, 
        srt_timestamp_to_timedelta(_start_ts),
        _end_ts, 
        srt_timestamp_to_timedelta(_end_ts),
        _prop)
    
    
def make_legal_content(content):
    r'''
    Remove illegal content from a content block. Illegal content includes:

    * Blank lines
    * Starting or ending with a newline

    .. doctest::

        >>> make_legal_content('\nfoo\n\nbar\n')
        'foo\nbar'

    :param str content: The content to make legal
    :returns: The legalised content
    :rtype: srt
    '''
    # We can't use content.splitlines() here since it does all sorts of stuff
    # that we don't want with \x1{c..e}, etc
    legal_content = '\n'.join(line for line in content.split('\n') if line)
    if legal_content != content:
        log.warning('Legalised content %r to %r', content, legal_content)
    return legal_content


def timedelta_to_srt_timestamp(timedelta_timestamp):
    r'''
    Convert a :py:class:`~datetime.timedelta` to an SRT timestamp.

    .. doctest::

        >>> import datetime
        >>> delta = datetime.timedelta(hours=1, minutes=23, seconds=4)
        >>> timedelta_to_srt_timestamp(delta)
        '01:23:04,000'

    :param datetime.timedelta timedelta_timestamp: A datetime to convert to an SRT timestamp
    :returns: The timestamp in SRT format
    :rtype: str
    '''

    hrs, secs_remainder = divmod(timedelta_timestamp.seconds, SECONDS_IN_HOUR)
    hrs += timedelta_timestamp.days * HOURS_IN_DAY
    mins, secs = divmod(secs_remainder, SECONDS_IN_MINUTE)
    msecs = timedelta_timestamp.microseconds // MICROSECONDS_IN_MILLISECOND
    return '%02d:%02d:%02d,%03d' % (hrs, mins, secs, msecs)

def split_timestamp(_ts):
    split_microsecond = _ts.split(",")
    split_time = split_microsecond[0].split(":")
    # print(split_time, split_microsecond[-1])
    return int(split_time[0]), int(split_time[1]), int(split_time[2]), int(split_microsecond[-1])

def srt_timestamp_to_timedelta(ts):
    r'''
    Convert an SRT timestamp to a :py:class:`~datetime.timedelta`.

    This function is *extremely* hot during parsing, so please keep perf in
    mind.

    .. doctest::

        >>> srt_timestamp_to_timedelta('01:23:04,000')
        datetime.timedelta(0, 4984)

    :param str ts: A timestamp in SRT format
    :returns: The timestamp as a :py:class:`~datetime.timedelta`
    :rtype: datetime.timedelta
    '''
    
    if len(ts) < TS_LEN:
        raise ValueError(
            'Expected timestamp length >= {}, but got {} (value: {})'.format(
                TS_LEN, len(ts), ts,
            )
        )
    '''
    # Doing this instead of splitting based on the delimiter using re.split
    # with a compiled regex or str.split is ~15% performance improvement during
    # parsing. We need to look from the end because the number of hours may be
    # >2 digits.
    '''
    hrs, mins, secs, msecs = (
        int(x) for x in [ts[:-10], ts[-9:-7], ts[-6:-4], ts[-3:]]
    )
    return timedelta(hours=hrs, minutes=mins, seconds=secs, milliseconds=msecs)
    
    '''
    print('\n')
    print(ts, split_timestamp(ts))
    hh, mm, ss, microseconds = split_timestamp(ts)
    print(type(hh), type(mm), type(ss), type(microseconds))
    if hh < 0 or 24 < hh :
        raise ValueError('Expected Hour(s) of timestamp 0 <= hh <= 24, but got {}'.format(hh))
    if mm < 0 or 59 < mm :
        raise ValueError('Expected Minute(s) of timestamp 0 <= mm <= 59, but got {}'.format(mm))
    if ss < 0 or 59 < ss :
        raise ValueError('Expected Second(s) of timestamp 0 <= ss <= 59, but got {}'.format(ss))
    if microseconds < 0 or 999 < microseconds:
        raise ValueError('Expected Microsecond(s) of timestamp 0 <= microseconds <= 999, but got{}'.format(microseconds))

    return timedelta(hours=hh, minutes=mm, seconds=ss, milliseconds=microseconds)
    '''

def sort_and_reindex(subtitles, start_index=1, in_place=False):
    '''
    Reorder subtitles to be sorted by start time order, and rewrite the indexes
    to be in that same order. This ensures that the SRT file will play in an
    expected fashion after, for example, times were changed in some subtitles
    and they may need to be resorted.

    .. doctest::

        >>> from datetime import timedelta
        >>> one = timedelta(seconds=1)
        >>> two = timedelta(seconds=2)
        >>> subs = [
        ...     Subtitle(index=999, start=one, end=one, content='1'),
        ...     Subtitle(index=0, start=two, end=two, content='2'),
        ... ]
        >>> list(sort_and_reindex(subs))  # doctest: +ELLIPSIS
        [Subtitle(...index=1...), Subtitle(...index=2...)]

    :param subtitles: :py:class:`Subtitle` objects in any order
    :param int start_index: The index to start from
    :param bool in_place: Whether to modify subs in-place for performance
                          (version <=1.0.0 behaviour)
    :returns: The sorted subtitles
    :rtype: :term:`generator` of :py:class:`Subtitle` objects
    '''
    skipped_subs = 0
    for sub_num, subtitle in enumerate(sorted(subtitles), start=start_index):
        if not in_place:
            subtitle = Subtitle(**vars(subtitle))

        try:
            _should_skip_sub(subtitle)
        except _ShouldSkipException as thrown_exc:
            log.warning(
                'Skipped subtitle at index %d: %s',
                subtitle.index_, thrown_exc,
            )
            skipped_subs += 1
            continue

        subtitle.index_ = sub_num - skipped_subs

        yield subtitle


def _should_skip_sub(subtitle):
    '''
    Check if a subtitle should be skipped based on the rules in
    SUBTITLE_SKIP_CONDITIONS.

    :param subtitle: A :py:class:`Subtitle` to check whether to skip
    :raises _ShouldSkipException: If the subtitle should be skipped
    '''
    for warning_msg, sub_skipper in SUBTITLE_SKIP_CONDITIONS:
        if sub_skipper(subtitle):
            raise _ShouldSkipException(warning_msg)


def parse(srt):
    r'''
    Convert an SRT formatted string (in Python 2, a :class:`unicode` object) to
    a :term:`generator` of Subtitle objects.

    This function works around bugs present in many SRT files, most notably
    that it is designed to not bork when presented with a blank line as part of
    a subtitle's content.

    .. doctest::

        >>> subs = parse("""\
        ... 422
        ... 00:31:39,931 --> 00:31:41,931
        ... Using mainly spoons,
        ...
        ... 423
        ... 00:31:41,933 --> 00:31:43,435
        ... we dig a tunnel under the city and release it into the wild.
        ...
        ... """)
        >>> list(subs)  # doctest: +ELLIPSIS
        [Subtitle(...index=422...), Subtitle(...index=423...)]

    :param str srt: Subtitles in SRT format
    :returns: The subtitles contained in the SRT file as py:class:`Subtitle`
              objects
    :rtype: :term:`generator` of :py:class:`Subtitle` objects
    '''

    expected_start = 0

    for match in SRT_REGEX.finditer(srt):
        actual_start = match.start()
        _raise_if_not_contiguous(srt, expected_start, actual_start)

        raw_index, raw_start_ts, raw_end_ts, proprietary, content = match.groups()
        yield Subtitle(
            index=int(raw_index), 
            start=raw_start_ts, 
            start_timedelta=srt_timestamp_to_timedelta(raw_start_ts),
            end=raw_end_ts,
            end_timedelta=srt_timestamp_to_timedelta(raw_end_ts),
            content=content.replace('\r\n', '\n'), 
            proprietary=proprietary,
        )

        expected_start = match.end()

    _raise_if_not_contiguous(srt, expected_start, len(srt))


def _raise_if_not_contiguous(srt, expected_start, actual_start):
    '''
    Raise :py:class:`SRTParseError` with diagnostic info if expected_start does
    not equal actual_start.

    :param str srt: The data being matched
    :param int expected_start: The expected next start, as from the last
                               iteration's match.end()
    :param int actual_start: The actual start, as from this iteration's
                             match.start()
    :raises SRTParseError: If the matches are not contiguous
    '''
    if expected_start != actual_start:
        unmatched_content = srt[expected_start:actual_start]
        raise SRTParseError(expected_start, actual_start, unmatched_content)


def compose(subtitles, reindex=True, start_index=1, strict=True, eol=None):
    r'''
    Convert an iterator of :py:class:`Subtitle` objects to a string of joined
    SRT blocks.

    .. doctest::

        >>> from datetime import timedelta
        >>> td = timedelta(seconds=1)
        >>> subs = [
        ...     Subtitle(index=1, start=td, end=td, content='x'),
        ...     Subtitle(index=2, start=td, end=td, content='y'),
        ... ]
        >>> compose(subs)  # doctest: +ELLIPSIS
        '1\n00:00:01,000 --> 00:00:01,000\nx\n\n2\n00:00:01,000 --> ...'

    :param subtitles: The subtitles to convert to SRT blocks
    :type subtitles: :term:`iterator` of :py:class:`Subtitle` objects
    :param bool reindex: Whether to reindex subtitles based on start time
    :param int start_index: If reindexing, the index to start reindexing from
    :param bool strict: Whether to enable strict mode, see
                        :py:func:`Subtitle.to_srt` for more information
    :param str eol: The end of line string to use (default "\n")
    :returns: A single SRT formatted string, with each input
              :py:class:`Subtitle` represented as an SRT block
    :rtype: str
    '''
    if reindex:
        subtitles = sort_and_reindex(subtitles, start_index=start_index)

    return ''.join(
        subtitle.to_srt(strict=strict, eol=eol) for subtitle in subtitles
    )


class SRTParseError(Exception):
    '''
    Raised when part of an SRT block could not be parsed.

    :param int expected_start: The expected contiguous start index
    :param int actual_start: The actual non-contiguous start index
    :param str unmatched_content: The content between the expected start index
                                  and the actual start index
    '''
    def __init__(self, expected_start, actual_start, unmatched_content):
        message = (
            'Expected contiguous start of match or end of input at char %d, '
            'but started at char %d (unmatched content: %r)' % (
                expected_start, actual_start, unmatched_content
            )
        )
        super(SRTParseError, self).__init__(message)

        self.expected_start = expected_start
        self.actual_start = actual_start
        self.unmatched_content = unmatched_content


class _ShouldSkipException(Exception):
    '''
    Raised when a subtitle should be skipped.
    '''
