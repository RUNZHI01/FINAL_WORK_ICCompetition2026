# UHD Images 4.6.0.0

This directory contains the official Ettus Research UHD images archive used with the NI USRP-2922 / N210 data-plane tests.

The upstream archive is split into 90 MiB parts to stay below the GitHub single-file limit:

```text
uhd-images_4.6.0.0.tar.xz.part-00
uhd-images_4.6.0.0.tar.xz.part-01
uhd-images_4.6.0.0.sha256
```

Reassemble and verify from the repository root:

```bash
bash board_deps/reassemble-large-files.sh
sha256sum board_deps/usrp/uhd-images/uhd-images_4.6.0.0.tar.xz
```

Expected SHA256 for `uhd-images_4.6.0.0.tar.xz`:

```text
a312587fbe9fffb6043cd96bae50ef283bb55a1e51e1435b5e4a350beb00e59d
```

The archive is from:

```text
https://github.com/EttusResearch/uhd/releases/tag/v4.6.0.0
```

The repository does not run an installer automatically. Extract the archive into the UHD images location used by the host that controls the USRP, or set `UHD_IMAGES_DIR` to the extracted `images` directory before running UHD tools.
