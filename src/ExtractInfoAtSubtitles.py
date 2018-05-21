import os
import codecs
import pprint	# pretty print
import logging

from operator import eq

import srt_github
from srt_github import make_a_subtitle
from smi2srt_github import convertSMI


class InfoOfSubtitle:
	raw_text_ = []
	subs_ = []
	extension_ = ''
	def __init__(self, _str_subtitle):
		# read subtitle
		logging.info(os.getcwd())
		logging.info("\n" + _str_subtitle)

		filename, extension = os.path.splitext(_str_subtitle)
		extension = extension.lower()
	
		if eq(extension, ".srt") : 
			with codecs.open(_str_subtitle, 'r', encoding="utf-8-sig") as f :
				raw_text_ = f.read()
				self.subs_ = list(srt_github.parse(raw_text_))
				extension_ = ".srt"
		elif eq(extension , ".smi") or eq(extension, ".sami"):
			with open(_str_subtitle) as f:
				raw_text_ = f.read()
				list_srt = convertSMI(raw_text_)
				temp_list_srt = []
				for idx, si in enumerate(list_srt):
					si.convertSrt()
					if si.contents_ == None or len(si.contents_) <= 0:
						continue
					tsi = make_a_subtitle(list_srt[idx].index_, 
						list_srt[idx].start_ts_,
						list_srt[idx].contents_,
						list_srt[idx].end_ts_
						)
					temp_list_srt.append(tsi)
				self.subs_ = temp_list_srt
				extension_ = ".smi"
