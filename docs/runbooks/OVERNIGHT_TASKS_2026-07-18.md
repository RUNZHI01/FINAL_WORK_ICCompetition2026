# Overnight Tasks - 2026-07-18

## P0: USRP Task Stop And Recovery

The cockpit needs a controlled stop path for an active USRP QPSK or IQ batch.
It must target the active job ID, stop the local runner and matching board-side
decode process, wait for both process trees to exit, and update the batch state
to `cancelled` rather than leaving the UI in `running`.

The recovery path must then restart or verify the persistent RX/TX controls
without stopping unrelated services. It should report each stage and require
both `100.121.87.73:29220` and `127.0.0.1:29221` to return `pong` before the
dashboard becomes ready.

Acceptance: cancel a QPSK batch during board decode, confirm no matching
decoder or local runner remains, preserve the RX/TX persistent services, and
start a new batch without a full Cockpit restart.

## P0: Startup Link Diagnostics

Add a bounded diagnostic command for the startup path. It must report the
board `eth0` address and route to `192.168.10.22`, RX USRP discovery, TX/RX
control-port reachability, and the relevant log tail. It must fail quickly
with the failing layer instead of waiting silently.
