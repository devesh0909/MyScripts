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

testcases = (

	(
		"read-around",
		("io", "read", "readdisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("io", "read", "readdisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("io", "read", "readcache"),
		),

	(
		"read-around",
		("disable", ),
		("io", "read", "readdisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("disable", ),
		("io", "read", "readdisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("disable", ),
		("io", "read", "eio"), # TBD
		),

	(
		"read-around",
		("reclaim", ),
		("io", "read", "readdisk"),
		),

	(
		"read-around",
		("reclaim", {'where_delay':3}),
		("io", "read", "readdisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("reclaim", ),
		("io", "read", "readdisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("reclaim", ),
		("io", "read", "readcache"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("reclaim", {'where_delay':3}),
		("io", "read", "readdisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("reclaim", {'where_delay':3}),
		("io", "read", "readcache"),
		),


	(
		"read-around",
		("disable", ),
		("reclaim", ),
		("io", "read", "readdisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("disable", ),
		("reclaim", ),
		("io", "read", "readdisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("disable", ),
		("reclaim", ),
		("io", "read", "eio"), #TBD
		),

	(
		"read-around",
		("io", "write", "writecache"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("io", "write", "writecache"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		),

	(
		"read-around",
		("disable", ),
		("io", "write", "writedisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("disable", ),
		("io", "write", "writedisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("disable", ),
		("io", "write", "writeinvalidate"),
		),

	(
		"read-around",
		("reclaim",),
		("io", "write", "writecache"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("reclaim",),
		("io", "write", "writecache"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("reclaim",),
		("io", "write", "writecache"),
		),

	(
		"read-around",
		("disable", ),
		("reclaim",),
		("io", "write", "writedisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("disable", ),
		("reclaim",),
		("io", "write", "writedisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("disable", ),
		("reclaim",),
		("io", "write", "writeinvalidate"),
		),
	
###

	(
		"read-around",
		("nospace", ),
		("io", "read", "readdisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("io", "read", "readdisk")
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("reclaim",),
		("io", "read", "readdisk")
		),

	(
		"read-around",
		("io", "write", "writecache"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("io", "read", "readcache"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("reclaim", {'where_delay':3}),
		("io", "read", "readcache"),
		),

	(
		"read-around", 
		("io", "write", "writecache"),
		("copyback", ),
		("reclaim", ),
		("io", "read", "readdisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("nospace", ),
		("io", "write", "writecache"),
		),

	)

concurrentio_testcases = (
	(
		"read-around",

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
		"read-around",
		("concurrent", True),
		("io", "read", "readdisk"),
		("io", "write", "writecache"),
		("concurrent", False),
		),

	(
		"read-around",
		("concurrent", True),
		("io", "read", "readdisk"),
		("io", "read", "readdisk"),
		("concurrent", False),
		),

	(
		# let's see if our code handles 10s of concurrent IOS

		"read-around",
		("concurrent", True),
		("io", "read", "readdisk"),
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
 		"read-around",
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("concurrent", True),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("io", "write", "writecache"),
		("concurrent", False),
		),

	(
		"read-around",
	 	("concurrent", True),
		("io", "read_partial", "readdisk"),
		("io", "read_partial", "readdisk"),
		("io", "write_partial", "writedisk"),
		("concurrent", False),
		),

	# (
	# 	"read-around",
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
		"read-around",
		("io", "read_partial", "readdisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("io", "read_partial", "readdisk"),
		),

	(
		"read-around",
		("disable", ),
		("io", "read_partial", "readdisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("disable", ),
		("io", "read_partial", "readdisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("disable", ),
		("io", "read_partial", "eio"),
		),
	(
		"read-around",
		("reclaim", ),
		("io", "read_partial", "readdisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("reclaim", ),
		("io", "read_partial", "readdisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("reclaim", ),
		("io", "read_partial", "readcache"),
		),

	(
		"read-around",
		("disable",),
		("reclaim", ),
		("io", "read_partial", "readdisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("disable",),
		("reclaim", ),
		("io", "read_partial", "readdisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("disable",),
		("reclaim", ),
		("io", "read_partial", "eio"), #TBD
		),

	(
		"read-around",
		("io", "write_partial", "writedisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("io", "write_partial", "writedisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("io", "write_partial", "writeinvalidate"),
		),

	(
		"read-around",
		("disable", ),
		("io", "write_partial", "writedisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("disable", ),
		("io", "write_partial", "writedisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("disable", ),
		("io", "write_partial", "writeinvalidate"),
		),

	(
		"read-around",
		("reclaim",),
		("io", "write_partial", "writedisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("reclaim",),
		("io", "write_partial", "writedisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("reclaim",),
		("io", "write_partial", "writeinvalidate"),
		),

	(
		"read-around",
		("disable", ),
		("reclaim",),
		("io", "write_partial", "writedisk"),
		),

	(
		"read-around",
		("io", "read", "readdisk"),
		("disable", ),
		("reclaim",),
		("io", "write_partial", "writedisk"),
		),

	(
		"read-around",
		("io", "write", "writecache"),
		("disable", ),
		("reclaim",),
		("io", "write_partial", "writeinvalidate"),
		),
	)
