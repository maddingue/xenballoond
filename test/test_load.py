import imp, sys, unittest

files = ["bin/xenballoond"]

class CheckLoad(unittest.TestCase):
	def test_load(self):
		for path in files:
			try:
				compile(open(path).read(), path, 'exec')
				self.assertTrue(1, "compiling %s" % path)
			except:
				self.assertTrue(0, "compiling %s" % path)


if __name__ == '__main__':
	unittest.main()
