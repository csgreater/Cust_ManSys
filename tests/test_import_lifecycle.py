import unittest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.import_lifecycle import processing_lease, recover_stale_batch, require_processing


class ImportLifecycleTests(unittest.TestCase):
    def test_old_worker_cannot_write_after_recovery_even_if_lease_connection_died(self):
        conn=MagicMock()
        cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value={'status':'failed'}
        with self.assertRaises(HTTPException): require_processing(conn,'batch')
        self.assertIn('FOR UPDATE',cur.execute.call_args.args[0])

    def connection(self, acquired=1, seconds=1000):
        conn=MagicMock()
        cur=conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect=[{'acquired':acquired},{'idle_seconds':seconds}]
        return conn,cur

    def test_live_worker_cannot_be_recovered(self):
        conn,cur=self.connection(acquired=0)
        with self.assertRaises(HTTPException) as error:
            with processing_lease(conn,'batch'): pass
        self.assertEqual(error.exception.status_code,409)
        self.assertFalse(any('DELETE' in call.args[0] for call in cur.execute.call_args_list))

    @patch('app.import_lifecycle.require_import_batch',return_value={'status':'processing'})
    def test_recent_batch_cannot_be_recovered(self, require):
        conn,cur=self.connection(seconds=100)
        with self.assertRaises(HTTPException): recover_stale_batch(conn,{},'batch')
        self.assertFalse(any('DELETE' in call.args[0] for call in cur.execute.call_args_list))

    @patch('app.import_lifecycle.require_import_batch',return_value={'status':'committing'})
    def test_never_cancel_commit_transaction(self, require):
        conn,cur=self.connection()
        with self.assertRaises(HTTPException): recover_stale_batch(conn,{},'batch')
        self.assertFalse(any('DELETE' in call.args[0] for call in cur.execute.call_args_list))

    @patch('app.import_lifecycle.require_import_batch',return_value={'status':'processing'})
    def test_stale_unlocked_batch_is_failed_and_committed_before_unlock(self, require):
        conn,cur=self.connection()
        result=recover_stale_batch(conn,{},'batch')
        self.assertEqual(result['status'],'failed')
        require.assert_called_once_with(conn,{},'batch',for_update=True)
        conn.commit.assert_called_once()
        mutations=[c for c in cur.execute.call_args_list if 'DELETE' in c.args[0] or 'UPDATE t_import_log' in c.args[0]]
        self.assertEqual(len(mutations),2)
        self.assertTrue(all(c.args[1]['batch']=='batch' for c in mutations))


if __name__=='__main__': unittest.main()
