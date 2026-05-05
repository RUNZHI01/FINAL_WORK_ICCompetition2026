import json, os, select, struct, time, zlib
RP='/dev/rpmsg0'
MAGIC=0x53434F4D
VERSION=1
MSG_JOB_REQ=1
MSG_JOB_ACK=2
MSG_HEARTBEAT=3
MSG_HEARTBEAT_ACK=4
MSG_JOB_DONE=5
MSG_STATUS_REQ=8
MSG_STATUS_RESP=9
HDR=struct.Struct('<IHHIIII')
JOBREQ=struct.Struct('<32sIII')
JOBACK=struct.Struct('<III')
HEART=struct.Struct('<IIII')
JOBDONE=struct.Struct('<IIII')
STATUS=struct.Struct('<IIIIII')
TRUSTED_SHA=bytes.fromhex('6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1')
def crc(magic, version, msg_type, seq, job_id, payload_len):
    return zlib.crc32(struct.pack('<IHHIII', magic, version, msg_type, seq, job_id, payload_len)) & 0xffffffff
def send_recv(fd, frame, timeout=2.0):
    try:
        while True:
            data=os.read(fd,4096)
            if not data:
                break
    except BlockingIOError:
        pass
    os.write(fd, frame)
    start=time.time(); rx=b''
    while time.time()-start < timeout:
        r,_,_=select.select([fd],[],[],0.2)
        if not r:
            continue
        try:
            chunk=os.read(fd,4096)
        except BlockingIOError:
            continue
        if chunk:
            rx += chunk
            if len(rx) >= HDR.size:
                break
    return rx
res={'rpmsg_exists': os.path.exists(RP)}
if not os.path.exists(RP):
    print(json.dumps(res, indent=2)); raise SystemExit(2)
fd=os.open(RP, os.O_RDWR | os.O_NONBLOCK)
try:
    job_id=9701
    job_payload=JOBREQ.pack(TRUSTED_SHA, 60000, 1, 3)
    job_frame=HDR.pack(MAGIC, VERSION, MSG_JOB_REQ, 1, job_id, len(job_payload), crc(MAGIC, VERSION, MSG_JOB_REQ, 1, job_id, len(job_payload))) + job_payload
    rx1=send_recv(fd, job_frame)
    res['job_req_tx_hex']=job_frame.hex(); res['job_ack_rx_hex']=rx1.hex(); res['job_ack_len']=len(rx1)
    if len(rx1) >= HDR.size + JOBACK.size:
        _, _, msg_type, _, _, payload_len, _ = HDR.unpack_from(rx1)
        if msg_type == MSG_JOB_ACK and payload_len == JOBACK.size:
            decision,fault_code,guard_state = JOBACK.unpack_from(rx1, HDR.size)
            res['job_ack']={'decision':decision,'fault_code':fault_code,'guard_state':guard_state}
    hb_payload=HEART.pack(2, 1234, 0, 100)
    hb_frame=HDR.pack(MAGIC, VERSION, MSG_HEARTBEAT, 2, job_id, len(hb_payload), crc(MAGIC, VERSION, MSG_HEARTBEAT, 2, job_id, len(hb_payload))) + hb_payload
    rx2=send_recv(fd, hb_frame)
    res['heartbeat_tx_hex']=hb_frame.hex(); res['heartbeat_ack_rx_hex']=rx2.hex(); res['heartbeat_ack_len']=len(rx2)
    jd_payload=JOBDONE.pack(0, 1, 0, 0)
    jd_frame=HDR.pack(MAGIC, VERSION, MSG_JOB_DONE, 3, job_id, len(jd_payload), crc(MAGIC, VERSION, MSG_JOB_DONE, 3, job_id, len(jd_payload))) + jd_payload
    rx3=send_recv(fd, jd_frame)
    res['job_done_tx_hex']=jd_frame.hex(); res['job_done_status_rx_hex']=rx3.hex(); res['job_done_status_len']=len(rx3)
    if len(rx3) >= HDR.size + STATUS.size:
        _, _, msg_type, _, _, payload_len, _ = HDR.unpack_from(rx3)
        if msg_type == MSG_STATUS_RESP and payload_len == STATUS.size:
            guard_state, active_job_id, last_fault_code, heartbeat_ok, sticky_fault, total_fault_count = STATUS.unpack_from(rx3, HDR.size)
            res['job_done_status']={'guard_state':guard_state,'active_job_id':active_job_id,'last_fault_code':last_fault_code,'heartbeat_ok':heartbeat_ok,'sticky_fault':sticky_fault,'total_fault_count':total_fault_count}
    status2=HDR.pack(MAGIC, VERSION, MSG_STATUS_REQ, 4, job_id, 0, crc(MAGIC, VERSION, MSG_STATUS_REQ, 4, job_id, 0))
    rx4=send_recv(fd, status2)
    res['status2_tx_hex']=status2.hex(); res['status2_rx_hex']=rx4.hex(); res['status2_len']=len(rx4)
    if len(rx4) >= HDR.size + STATUS.size:
        _, _, msg_type, _, _, payload_len, _ = HDR.unpack_from(rx4)
        if msg_type == MSG_STATUS_RESP and payload_len == STATUS.size:
            guard_state, active_job_id, last_fault_code, heartbeat_ok, sticky_fault, total_fault_count = STATUS.unpack_from(rx4, HDR.size)
            res['status2']={'guard_state':guard_state,'active_job_id':active_job_id,'last_fault_code':last_fault_code,'heartbeat_ok':heartbeat_ok,'sticky_fault':sticky_fault,'total_fault_count':total_fault_count}
    print(json.dumps(res, indent=2))
finally:
    os.close(fd)
