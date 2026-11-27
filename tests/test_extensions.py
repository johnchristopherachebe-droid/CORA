import tempfile, unittest, os, sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cora.security import ApprovalAuthority
from cora.upgrade_manager import UpgradeManager
from cora.research_workspace import ResearchWorkspace
from cora.local_model import LocalModel

class ExtensionTests(unittest.TestCase):
    def test_owner_approval_signature(self):
        a = ApprovalAuthority("x"*40)
        token = a.issue("deploy-1", "owner-1")
        self.assertTrue(a.verify(token, "deploy-1", "owner-1"))
        self.assertFalse(a.verify(token, "deploy-1", "someone-else"))
        self.assertFalse(a.verify(token, "deploy-2", "owner-1"))

    def test_upgrade_requires_owner_and_tests_and_rejects_stale(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); (base/"app.py").write_text("x=1\n")
            m=UpgradeManager(base, base/"proposals")
            p=m.propose("app.py", "x=2\n")
            with self.assertRaises(PermissionError):
                m.approve_and_apply(p.proposal_id, owner_authenticated=False, approval_valid=False,
                                    test_report={"passed":True,"tests_run":1})
            with self.assertRaises(ValueError):
                m.approve_and_apply(p.proposal_id, owner_authenticated=True, approval_valid=True,
                                    test_report={"passed":True,"tests_run":0})
            (base/"app.py").write_text("x=3\n")
            with self.assertRaises(RuntimeError):
                m.approve_and_apply(p.proposal_id, owner_authenticated=True, approval_valid=True,
                                    test_report={"passed":True,"tests_run":1})

    def test_upgrade_blocks_secrets_and_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d); (base/"app.py").write_text("x=1")
            m=UpgradeManager(base, base/"proposals")
            for path in ("../escape.py", ".env", "secrets/key.txt"):
                with self.assertRaises(ValueError):
                    m.propose(path, "bad")

    def test_research_filters_non_http_urls_and_persists_tabs(self):
        with tempfile.TemporaryDirectory() as d:
            w=ResearchWorkspace(Path(d)/"r.db",
                lambda q: [{"title":"A","url":"https://example.org/a","snippet":"ok"},
                           {"title":"bad","url":"file:///etc/passwd"}],
                lambda q: [{"title":"Video","url":"https://video.example/watch"}])
            item=w.create("test query")
            self.assertEqual(len(item["payload"]["sources"]),1)
            self.assertEqual(len(item["payload"]["videos"]),1)
            self.assertEqual(w.get(item["id"])["query"],"test query")
            self.assertEqual(len(w.list()),1)

    def test_local_model_rejects_remote_http(self):
        with self.assertRaises(ValueError):
            LocalModel("http://example.com")

if __name__ == "__main__":
    unittest.main()
