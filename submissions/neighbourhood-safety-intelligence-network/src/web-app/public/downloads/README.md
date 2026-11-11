# Android APK downloads

The landing page's "Get the Android App" section checks for `neighbourhood-safety.apk` in this folder.
APKs are build artifacts and are not committed. To enable the download button locally:

```bash
cd src/android
gradle :app:assembleDebug
cp app/build/outputs/apk/debug/app-debug.apk ../web-app/public/downloads/neighbourhood-safety.apk
```

For a hosted build, set `VITE_ANDROID_DOWNLOAD_URL` in `src/web-app/.env` to a GitHub Release asset URL instead.
