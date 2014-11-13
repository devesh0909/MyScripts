#!/usr/bin/python

#
#  Copyright 2012 Cachebox, Inc. All rights reserved. This software
#  is property of Cachebox, Inc and contains trade secrects,
#  confidential & proprietary information. Use, disclosure or copying
#  this without explicit written permission from Cachebox, Inc is
#  prohibited.
#
#  Author: Cachebox, Inc (sales@cachebox.com)
#

flowcodes = {
	"readpopulate":1,
	"writeinvalidate":2,
	"readcache":3,
	"writecache":4,
	"readdisk":5,
	"writedisk":6,
	"writethrough":7,
	"copyback":8,
	"deferred_io":9,
	"eio":255
	}

iflowcodes = {v:k for k, v in flowcodes.items()}

rwdict = {
	0:'read',
	1:'write'
}

testcases = (

	(
		"write-back",
		("io", "read", "readpopulate"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("io", "read", "readcache"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("io", "read", "readcache"),
		),

	(
		"write-back",
		("disable", ),
		("io", "read", "readdisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("disable", ),
		("io", "read", "readdisk"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("disable", ),
		("io", "read", "eio"), # TBD
		),

	(
		"write-back",
		("reclaim", ),
		("io", "read", "readdisk"),
		),

	(
		"write-back",
		("reclaim", {'where_delay':3}),
		("io", "read", "readdisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("reclaim", ),
		("io", "read", "readpopulate"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("reclaim", ),
		("io", "read", "readcache"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("reclaim", {'where_delay':3}),
		("io", "read", "readcache"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("reclaim", {'where_delay':3}),
		("io", "read", "readcache"),
		),


	(
		"write-back",
		("disable", ),
		("reclaim", ),
		("io", "read", "readdisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("disable", ),
		("reclaim", ),
		("io", "read", "readdisk"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("disable", ),
		("reclaim", ),
		("io", "read", "eio"), #TBD
		),

	(
		"write-back",
		("io", "write", "writecache"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("io", "write", "writecache"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		),

	(
		"write-back",
		("disable", ),
		("io", "write", "writedisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("disable", ),
		("io", "write", "writeinvalidate"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("disable", ),
		("io", "write", "writeinvalidate"),
		),

	(
		"write-back",
		("reclaim",),
		("io", "write", "writecache"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("reclaim",),
		("io", "write", "writecache"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("reclaim",),
		("io", "write", "writecache"),
		),

	(
		"write-back",
		("disable", ),
		("reclaim",),
		("io", "write", "writedisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("disable", ),
		("reclaim",),
		("io", "write", "writeinvalidate"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("disable", ),
		("reclaim",),
		("io", "write", "writeinvalidate"),
		),
	
###

	(
		"write-back",
		("nospace", ),
		("io", "read", "readdisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("io", "read", "readcache")
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("reclaim",),
		("io", "read", "readpopulate")
		),

	(
		"write-back",
		("io", "write", "writecache"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("io", "read", "readcache"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("reclaim", {'where_delay':3}),
		("io", "read", "readcache"),
		),

	(
		"write-back", 
		("io", "write", "writecache"),
		("copyback", ),
		("reclaim", ),
		("io", "read", "readpopulate"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("nospace", ),
		("io", "write", "writecache"),
		),

	)

concurrentio_testcases = (
	(
		"write-back",

		# setup concurrent IOs
		("concurrent", True),

		# push the first IO through, this will serialize all
		# other IOs.

		("io", "write", "writecache"),

		# now push another IO on the same hdd offset, will be
		# serialized.

		("io", "write", "writecache"),

		# unblock all IOs, the first IO will be processed now
		# and will 'release' other ios, eventually both IOs
		# will complete.

		("concurrent", False),
		),

	(
		"write-back",
		("concurrent", True),
		("io", "read", "readpopulate"),
		("io", "write", "writecache"),
		("concurrent", False),
		),

	(
		"write-back",
		("concurrent", True),
		("io", "read", "readpopulate"),
		("io", "read", "readcache"),
		("concurrent", False),
		),

	(
		# let's see if our code handles 10s of concurrent IOS

		"write-back",
		("concurrent", True),
		("io", "read", "readpopulate"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("concurrent", False),
		),

 	(
 		"write-back",
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("concurrent", True),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("concurrent", False),
		),

	(
		"write-back",
	 	("concurrent", True),
		("io", "read_partial", "readdisk"),
		("io", "read_partial", "readdisk"),
		("io", "write_partial", "writedisk"),
		("concurrent", False),
		),

	# (
	# 	"write-back",
	# 	("io", "write", "writecache"),
	# 	("io", "write", "writecache"),
	# 	("concurrent", True),
	# 	("io", "write", "writecache"),
	# 	("io", "write", "writecache"),
	# 	("copyback", ),
	# 	("io", "write", "writecache"),
	# 	("concurrent", False),
	# 	),
	)

partialio_testcases = (
	(
		"write-back",
		("io", "read_partial", "readdisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("io", "read_partial", "readcache"),
		),

	(
		"write-back",
		("disable", ),
		("io", "read_partial", "readdisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("disable", ),
		("io", "read_partial", "readdisk"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("disable", ),
		("io", "read_partial", "eio"),
		),
	(
		"write-back",
		("reclaim", ),
		("io", "read_partial", "readdisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("reclaim", ),
		("io", "read_partial", "readdisk"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("reclaim", ),
		("io", "read_partial", "readcache"),
		),

	(
		"write-back",
		("disable",),
		("reclaim", ),
		("io", "read_partial", "readdisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("disable",),
		("reclaim", ),
		("io", "read_partial", "readdisk"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("disable",),
		("reclaim", ),
		("io", "read_partial", "eio"), #TBD
		),

	(
		"write-back",
		("io", "write_partial", "writedisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("io", "write_partial", "writecache"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("io", "write_partial", "writecache"),
		),

	(
		"write-back",
		("disable", ),
		("io", "write_partial", "writedisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("disable", ),
		("io", "write_partial", "writeinvalidate"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("disable", ),
		("io", "write_partial", "writeinvalidate"),
		),

	(
		"write-back",
		("reclaim",),
		("io", "write_partial", "writedisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("reclaim",),
		("io", "write_partial", "writedisk"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("reclaim",),
		("io", "write_partial", "writeinvalidate"),
		),

	(
		"write-back",
		("disable", ),
		("reclaim",),
		("io", "write_partial", "writedisk"),
		),

	(
		"write-back",
		("io", "read", "readpopulate"),
		("disable", ),
		("reclaim",),
		("io", "write_partial", "writeinvalidate"),
		),

	(
		"write-back",
		("io", "write", "writecache"),
		("disable", ),
		("reclaim",),
		("io", "write_partial", "writeinvalidate"),
		),
	)
	
