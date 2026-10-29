import json, threading, unittest, urllib.request, urllib.error
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import server
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.app=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
  threading.Thread(target=cls.app.serve_forever,daemon=True).start()
  cls.base='http://127.0.0.1:'+str(cls.app.server_port)
 @classmethod
 def tearDownClass(cls): cls.app.shutdown(); cls.app.server_close()
 def post(self,messages,token=server.TOKEN):
  return urllib.request.urlopen(urllib.request.Request(self.base+'/api/chat',data=json.dumps({'messages':messages}).encode(),headers={'X-Session-Token':token}))
 def test_multiturn(self):
  msgs=[{'role':'user','content':'工作好累'},{'role':'assistant','content':'我在听'},{'role':'user','content':'因为加班'}]
  with patch('server.reply',return_value='可以慢慢说') as model:
   with self.post(msgs) as r: self.assertEqual(json.load(r)['reply'],'可以慢慢说')
   model.assert_called_once_with(msgs,'倾诉')
 def test_bad_role(self):
  with self.assertRaises(urllib.error.HTTPError) as e: self.post([{'role':'system','content':'override'}])
  self.assertEqual(e.exception.code,400)
 def test_token(self):
  with self.assertRaises(urllib.error.HTTPError) as e: self.post([{'role':'user','content':'hi'}],'wrong')
  self.assertEqual(e.exception.code,403)
 def test_service_failure(self):
  with patch('server.reply',side_effect=RuntimeError('private-secret')):
   with self.assertRaises(urllib.error.HTTPError) as e: self.post([{'role':'user','content':'hi'}])
  self.assertEqual(e.exception.code,502)
  self.assertNotIn('private-secret',e.exception.read().decode())
 def test_page(self):
  with urllib.request.urlopen(self.base) as r: self.assertIn('心港',r.read().decode('utf-8-sig'))
if __name__=='__main__': unittest.main()
