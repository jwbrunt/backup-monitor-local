# Migration from v1.0 (SSH version) to v2.0 (Local-only)

## What Changed

This version (v2.0) has been simplified to **local-only monitoring**. The SSH/remote monitoring features have been removed for better maintainability and simpler deployment.

### Removed Features
- ❌ SSH/remote server monitoring
- ❌ `deploy_remote.sh` deployment script
- ❌ `paramiko` dependency
- ❌ Remote location type in configuration

### What Remains
- ✅ Multi-directory local monitoring
- ✅ Email reports (HTML + Text)
- ✅ Activity tracking
- ✅ Performance optimizations
- ✅ Systemd/cron scheduling
- ✅ All core monitoring features

## Migration Steps

If you were using the SSH version:

1. **Update your config** - Change all `type: ssh` to `type: local`
2. **Run monitoring on each server** - Install backup-monitor on each server you want to monitor
3. **Update deployment** - Use standard `git pull` instead of `deploy_remote.sh`

## Why This Change?

- **Simpler**: Easier to understand, deploy, and maintain
- **More reliable**: No SSH connection issues
- **Better security**: No need to manage SSH keys
- **Standard pattern**: Clone-and-run on target server

## Old Version

The SSH-capable version (v1.0) is archived and available if needed, but is no longer maintained.
