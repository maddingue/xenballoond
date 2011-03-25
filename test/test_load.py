import sys, unittest

sys.path += "lib"
modules=["xenballoond.xenballoon"]

class CheckLoad(unittest.TestCase):
    def test_load(self):
        for module in modules:
            try:
                __import__(module)
                self.assertTrue(1, "loading %s" % module)
            except:
                self.assertTrue(0, "loading %s" % module)


if __name__ == "__main__":
    unittest.main()

