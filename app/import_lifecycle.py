"""Recover explicitly selected abandoned parses without cancelling live workers."""
from contextlib import contextmanager
import hashlib

from fastapi import HTTPException
from app.import_access import require_import_batch


def require_processing(conn,batch_no):
    """Fence every parser write with the batch row in the same transaction."""
    with conn.cursor() as cur:
        cur.execute('SELECT status FROM t_import_log WHERE batch_no=%(batch)s FOR UPDATE',{'batch':batch_no})
        row=cur.fetchone()
    if not row or row['status']!='processing':
        raise HTTPException(409,'批次状态已变化，旧解析任务已停止')


@contextmanager
def processing_lease(conn, batch_no):
    name='import_parse_'+hashlib.sha256(batch_no.encode()).hexdigest()[:40]
    with conn.cursor() as cur:
        cur.execute('SELECT GET_LOCK(%(name)s,0) AS acquired',{'name':name})
        if cur.fetchone()['acquired'] != 1:
            raise HTTPException(409,'该批次仍有工作线程运行，请稍后查看进度')
        try:
            yield
        finally:
            cur.execute('SELECT RELEASE_LOCK(%(name)s)',{'name':name})


def recover_stale_batch(conn,user,batch_no,*,min_idle_seconds=900):
    with processing_lease(conn,batch_no):
        log=require_import_batch(conn,user,batch_no,for_update=True)
        if log['status']!='processing':
            raise HTTPException(409,'仅可恢复中断的解析批次，请刷新状态')
        with conn.cursor() as cur:
            cur.execute('SELECT TIMESTAMPDIFF(SECOND,import_time,NOW()) AS idle_seconds FROM t_import_log WHERE batch_no=%(batch)s',{'batch':batch_no})
            if cur.fetchone()['idle_seconds']<max(900,min_idle_seconds):
                raise HTTPException(409,'批次最后进度距今不足 15 分钟，请稍后重试')
            cur.execute('DELETE FROM tmp_order_import WHERE batch_no=%(batch)s',{'batch':batch_no})
            cur.execute("""UPDATE t_import_log SET status='failed',import_time=NOW(),
              remark='解析任务已中断，已释放批次；请重新上传源文件' WHERE batch_no=%(batch)s""",{'batch':batch_no})
        # Mutations become visible before another worker can acquire the lease.
        conn.commit()
    return {'batch_no':batch_no,'status':'failed'}
