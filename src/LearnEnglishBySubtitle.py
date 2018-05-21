#-*- coding: utf-8 -*-

# ts : timestamp

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import os
from operator import eq

import pprint # pretty print
import logging
logging.basicConfig(filename='python_logging.log', level=logging.DEBUG)
import ExtractInfoAtSubtitles

## Find Extension Format
def isSupportedExtension(_str_extension):
	str_lower_extension = _str_extension.lower()
	logging.info("Input extension : " + str_lower_extension)
	ret_val = False
	if eq(str_lower_extension, ".smi") or eq(str_lower_extension, ".sami") :
		ret_val = True
	elif eq(str_lower_extension, ".srt") :
		ret_val = True
	return ret_val


def findExtension(_str_subtitle):
	# find extension of input 
	filename, extension = os.path.splitext(_str_subtitle)

	# is support now?
	is_support = isSupportedExtension(extension)
	if is_support :
		return extension
	else :
		logging.error("\n Filename : " + _str_subtitle + " IS NOT SUPPORT")
		return ""


def deltatime_2_timestamp(_deltatime):
	return _deltatime.total_seconds() + (_deltatime.microseconds / 1000000)


def writeSrt(_output_filename, _srt_info):	
	ndx = 1
	with open(_output_filename, 'w') as f:
		# write (SRT format)
		for srt in _srt_info:	
			str_srt = '%d\n%s --> %s\n%s\n%s\n\n' % (ndx, srt['left_ts'], srt['right_ts'], srt['f_contents'], srt['s_contents'])
			f.write(str_srt)
			ndx += 1


def getMin(_f, _s):
	if _f >= _s:
		return _s
	else:
		return _f


def getMax(_f, _s):
	if _f <= _s:
		return _s
	else:
		return _f


def getMinSetReturn(_f, _s, _f_value, _s_value):
	return _f_value if _f <= _s else _s_value


def getMaxSetReturn(_f, _s, _f_value, _s_value):
	return _f_value if _f >= _s else _s_value


def doWork(_first_subtitle, _second_subtitle, _output_filename):
	first_extension = findExtension(_first_subtitle)
	second_extension = findExtension(_second_subtitle)

	### is supported format?
	if not eq(first_extension, "") or not eq(second_extension, "") :	
		logging.info('\n\n')
		logging.info(" FIRST SUBTITLE \n")
		first_sub = ExtractInfoAtSubtitles.InfoOfSubtitle(_first_subtitle)
		logging.debug(first_sub.subs_)

		logging.info('\n\n')
		logging.info(" SECOND SUBTITLE \n")
		second_sub = ExtractInfoAtSubtitles.InfoOfSubtitle(_second_subtitle)
		logging.debug(second_sub.subs_)

		# Compare
		all_matched_list = []
		for f_idx, f_val in enumerate(first_sub.subs_):
			# logging.debug("[IDX] : {%04d}, [START] : {%05d, %06d}, [END] : {%05d, %06d}\n" % (f_idx, f_val.start_timedelta_.total_seconds(), f_val.start_timedelta_.microseconds, f_val.end_timedelta_.total_seconds(), f_val.end_timedelta_.microseconds))
			# td : timedelta
			f_start_td = deltatime_2_timestamp(f_val.start_timedelta_) 
			f_end_td = deltatime_2_timestamp(f_val.end_timedelta_) 

			matched_row_list = []
			for s_idx, s_val in enumerate(second_sub.subs_):
				s_start_td = deltatime_2_timestamp(s_val.start_timedelta_) 
				s_end_td = deltatime_2_timestamp(s_val.end_timedelta_) 

				# get start (end) of matched timestamp
				l_ts = f_start_td if f_start_td >= s_start_td else s_start_td
				r_ts = f_end_td if f_end_td <= s_end_td else s_end_td
				if l_ts < r_ts :
					logging.info("[1] : {%.3f} {%.3f} {%.3f} {%.3f}, {%.3f} {%.3f} {%s} {%s}" % (f_start_td, f_end_td, s_start_td, s_end_td, l_ts, r_ts, str(unicode(f_val.contents_)), str(unicode(s_val.contents_))))
					matched_row = {	"f_start": f_start_td,
									"f_end": f_end_td,
									"s_start": s_start_td,
									"s_end": s_end_td,
									"left_ts": l_ts, 
									"right_ts": r_ts, 
									"f_contents": str(unicode(f_val.contents_)), 
									"s_contents": str(unicode(s_val.contents_))
									}
					matched_row_list.append(matched_row)
			'''
			# if need merge
			arrange_matched = []
			if len(matched_row_list) >= 2:
				is_merged = False
				for idx in range(len(matched_row_list)):
					if idx != len(matched_row_list) - 1 and not is_merged :
						left_ts = getMin(matched_row_list[idx]['f_start'], matched_row_list[idx]['s_start'])
						left_ts = getMin(left_ts, matched_row_list[idx + 1]['s_start'])

						right_ts = getMax(matched_row_list[idx]['f_end'], matched_row_list[idx]['s_end'])
						right_ts = getMax(right_ts, matched_row_list[idx + 1]['s_end'])

						print('\n')
						print(matched_row_list[idx]['f_contents'])
						print(matched_row_list[idx]['s_contents'])
						print(matched_row_list[idx + 1]['s_contents'])
						matched_row = {
										"left_ts": left_ts,
										"right_ts": right_ts,
										"f_contents": str(unicode(matched_row_list[idx]['f_contents'])),
										"s_contents": str(unicode(matched_row_list[idx]['s_contents'] + matched_row_list[idx + 1]['s_contents']))
										}
						is_merged = True
						arrange_matched.append(matched_row)
					else:
						if not is_merged:
							arrange_matched.append(matched_row_list[idx])
							is_merged = False
					# print(idx)
			'''
			# if exist matched times
			if len(matched_row_list) > 0:
				for idx in matched_row_list:
					all_matched_list.append(idx)

		# write srt
		writeSrt(_output_filename, all_matched_list)
		

if __name__=="__main__":
	# get length of arguments
	len_of_arguments = len(sys.argv)

	'''
	sys.argv[1] : first subtitle
	sys.argv[2] : second subtitle
	sys.argv[3] : output filename
	'''
	logging.info("[INPUT ARGUMENTS]")
	for idx in range(len_of_arguments):
		logging.info(sys.argv[idx])

	if len_of_arguments < 2:
		first_subtitle = "../res/Transformers_Revenge_Of_The_Fallen_2009_3Li_BluRay_English.srt"
	else:
		first_subtitle = sys.argv[1]

	if len_of_arguments < 3:
		second_subtitle = "../res/Transformers_Revenge_Of_The_Fallen_2009_3Li_BluRay_Korean.srt"
	else:
		second_subtitle = sys.argv[2]

	if len_of_arguments < 4:
		# output_filename = "../res/Transformers_Revenge_Of_The_Fallen_2009_3Li_BluRay_output.srt"
		output_filename = sys.argv[1]
		index_of_last_point = output_filename.rfind('.')
		output_filename = output_filename[0:index_of_last_point] + "_output_.srt"
	else:
		output_filename = sys.argv[3]

	doWork(first_subtitle, second_subtitle, output_filename)











