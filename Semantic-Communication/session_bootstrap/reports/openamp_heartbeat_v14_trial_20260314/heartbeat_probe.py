import json, os, select, struct, time, zlib
RP='/dev/rpmsg0'
MAGIC=0x53434F4D
VERSION=1
MSG_JOB_REQ=1
MSG_JOB_ACK=2
MSG_HEARTBEAT=3
MSG_HEARTBEAT_ACK=4
MSG_STATUS_REQ=8
MSG_STATUS_RESP=9
HDR=struct.Struct('<IHHIIII')
JOBREQ=struct.Struct('<32sIII')
JOBACK=struct.Struct('<III')
HEART=struct.Struct('<IIII')
HEARTACK=struct.Struct('<II')
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
    print(json.dumps(res,indent=2)); raise SystemExit(2)
fd=os.open(RP, os.O_RDWR | os.O_NONBLOCK)
try:
    job_id=9301
    job_payload=JOBREQ.pack(TRUSTED_SHA, 60000, 1, 3)
    job_frame=HDR.pack(MAGIC, VERSION, MSG_JOB_REQ, 1, job_id, len(job_payload), crc(MAGIC, VERSION, MSG_JOB_REQ, 1, job_id, len(job_payload))) + job_payload
    rx=send_recv(fd, job_frame)
    res['job_req_tx_hex']=job_frame.hex(); res['job_ack_rx_hex']=rx.hex(); res['job_ack_len']=len(rx)
    if len(rx) >= HDR.size + JOBACK.size:
        magic, version, msg_type, seq, got_job_id, payload_len, hcrc = HDR.unpack_from(rx)
        res['job_ack_hdr']={'magic':magic,'version':version,'msg_type':msg_type,'seq':seq,'job_id':got_job_id,'payload_len':payload_len,'header_crc32':hcrc}
        if msg_type == MSG_JOB_ACK and payload_len == JOBACK.size:
            decision,fault_code,guard_state = JOBACK.unpack_from(rx, HDR.size)
            res['job_ack']={'decision':decision,'fault_code':fault_code,'guard_state':guard_state}
    hb_payload=HEART.pack(2, 1234, 0, 100)
    hb_frame=HDR.pack(MAGIC, VERSION, MSG_HEARTBEAT, 2, job_id, len(hb_payload), crc(MAGIC, VERSION, MSG_HEARTBEAT, 2, job_id, len(hb_payload))) + hb_payload
    rx2=send_recv(fd, hb_frame)
    res['heartbeat_tx_hex']=hb_frame.hex(); res['heartbeat_ack_rx_hex']=rx2.hex(); res['heartbeat_ack_len']=len(rx2)
    if len(rx2) >= HDR.size + HEARTACK.size:
        magic, version, msg_type, seq, got_job_id, payload_len, hcrc = HDR.unpack_from(rx2)
        res['heartbeat_ack_hdr']={'magic':magic,'version':version,'msg_type':msg_type,'seq':seq,'job_id':got_job_id,'payload_len':payload_len,'header_crc32':hcrc}
        if msg_type == MSG_HEARTBEAT_ACK and payload_len == HEARTACK.size:
            guard_state, heartbeat_ok = HEARTACK.unpack_from(rx2, HDR.size)
            res['heartbeat_ack']={'guard_state':guard_state,'heartbeat_ok':heartbeat_ok}
    status_frame=HDR.pack(MAGIC, VERSION, MSG_STATUS_REQ, 3, job_id, 0, crc(MAGIC, VERSION, MSG_STATUS_REQ, 3, job_id, 0))
    rx3=send_recv(fd, status_frame)
    res['status_req_tx_hex']=status_frame.hex(); res['status_resp_rx_hex']=rx3.hex(); res['status_resp_len']=len(rx3)
    if len(rx3) >= HDR.size + STATUS.size:
        magic, version, msg_type, seq, got_job_id, payload_len, hcrc = HDR.unpack_from(rx3)
        res['status_resp_hdr']={'magic':magic,'version':version,'msg_type':msg_type,'seq':seq,'job_id':got_job_id,'payload_len':payload_len,'header_crc32':hcrc}
        if msg_type == MSG_STATUS_RESP and payload_len == STATUS.size:
            guard_state, active_job_id, last_fault_code, heartbeat_ok, sticky_fault, total_fault_count = STATUS.unpack_from(rx3, HDR.size)
            res['status_resp']={'guard_state':guard_state,'active_job_id':active_job_id,'last_fault_code':last_fault_code,'heartbeat_ok':heartbeat_ok,'sticky_fault':sticky_fault,'total_fault_count':total_fault_count}
    print(json.dumps(res, indent=2))
finally:
    os.close(fd)
