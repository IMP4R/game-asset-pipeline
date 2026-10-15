import unittest,tempfile,json
from pathlib import Path
from critic import validate_manifest,validate_review,parse_review
from review_gate import accepted_review,digest
class CriticContracts(unittest.TestCase):
 def test_validate_review_and_reject_unread(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'source.png').write_bytes(b'source');(root/'candidate.png').write_bytes(b'candidate')
   m={'items':[{'id':'object','files':['source.png','candidate.png']}]}
   r={'stage':'assets','verdict':'pass','reviewed_files':['source.png','candidate.png'],'items':[{'id':'object','verdict':'pass','evidence':['source and candidate match']}],'issues':[]}
   validate_review(root,'assets',m,r,{'source.png','candidate.png'})
   with self.assertRaises(ValueError):validate_review(root,'assets',m,r,{'source.png'})
   r['items'][0]['verdict']='revise'
   with self.assertRaises(ValueError):validate_review(root,'assets',m,r,{'source.png','candidate.png'})
 def test_accepted_review_stale_and_newer_reject(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'a').write_text('a');out=root/'output/critics';out.mkdir(parents=True)
   (out/'geometry-1.json').write_text(json.dumps({'stage':'geometry','verdict':'pass','file_hashes':{'a':digest(root/'a')}}))
   accepted_review(root,'geometry');(root/'a').write_text('b')
   with self.assertRaises(ValueError):accepted_review(root,'geometry')
 def test_validate_manifest_path_escape(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):validate_manifest(Path(d),{'items':[{'id':'a','files':['../escape']}]})
 def test_parse_review(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'trace';p.write_text(json.dumps({'type':'message_end','message':{'role':'assistant','content':[{'type':'text','text':'{"verdict":"revise"}'}]}})+'\n')
   self.assertEqual(parse_review(p)[0]['verdict'],'revise')
if __name__=='__main__':unittest.main()
