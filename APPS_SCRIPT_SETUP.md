# Apps Script OTP Email Setup - COMPLETED ✅

## Configuration Details

### 1. Apps Script Deployment
- **Web App URL:** `https://script.google.com/macros/s/AKfycby0z8cq7XWKBM7BuoXRV9lBBA8YS2wFNFOlZ8YYCeZifjloaiIvXE-45vfKiEDLZ4Wd/exec`
- **Deployment ID:** `AKfycby0z8cq7XWKBM7BuoXRV9lBBA8YS2wFNFOlZ8YYCeZifjloaiIvXE-45vfKiEDLZ4Wd`

### 2. Shared Secret
```
bengo-otp-secret-2026-secure-key-xyz789
```

### 3. Django Settings (Already Configured)
Located in: `backend/config/settings.py`

```python
APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycby0z8cq7XWKBM7BuoXRV9lBBA8YS2wFNFOlZ8YYCeZifjloaiIvXE-45vfKiEDLZ4Wd/exec'
APPS_SCRIPT_SECRET = 'bengo-otp-secret-2026-secure-key-xyz789'
```

### 4. Apps Script Code (Already Updated)
Located in: `backend/OTP_EmailScript.gs`

The constant `EXPECTED_SECRET` has been set to match Django's secret:
```javascript
const EXPECTED_SECRET = 'bengo-otp-secret-2026-secure-key-xyz789';
```

---

## ⚠️ IMPORTANT: Final Step

**You MUST update the Apps Script deployment with the new code:**

1. Open your Apps Script project: https://script.google.com/
2. Replace the `Code.gs` content with the updated code from `OTP_EmailScript.gs`
3. Click **"Deploy"** → **"Manage deployments"**
4. Click the **edit icon (pencil)** next to your web app deployment
5. Change **"Version"** to **"New version"**
6. Click **"Deploy"**

The URL will remain the same, but the script will now use the correct secret validation.

---

## Testing

### Test from Browser
Visit: https://script.google.com/macros/s/AKfycby0z8cq7XWKBM7BuoXRV9lBBA8YS2wFNFOlZ8YYCeZifjloaiIvXE-45vfKiEDLZ4Wd/exec

You should see a status page showing the service is running.

### Test Email Sending
```bash
curl -X POST "https://script.google.com/macros/s/AKfycby0z8cq7XWKBM7BuoXRV9lBBA8YS2wFNFOlZ8YYCeZifjloaiIvXE-45vfKiEDLZ4Wd/exec" \
  -d "email=your-email@example.com" \
  -d "otp=123456" \
  -d "secret=bengo-otp-secret-2026-secure-key-xyz789"
```

### Test from Registration Page
1. Start Django server: `python manage.py runserver`
2. Start frontend: `npm run dev` (in frontend folder)
3. Go to registration page
4. Enter an email and request OTP
5. Check your email inbox for the verification code

---

## Security Notes

- The shared secret prevents unauthorized use of your email sending endpoint
- Never commit the secret to public repositories
- For production, use environment variables instead of hardcoded values
- The Apps Script runs under your Google account permissions

---

## Troubleshooting

**If emails aren't sending:**
1. Check Apps Script logs: Script editor → "Executions"
2. Verify the secret matches in both places
3. Ensure deployment is updated to latest version
4. Check Gmail sending limits (500 emails/day for personal accounts)

**If you see "Unauthorized" errors:**
- Secret mismatch between Django and Apps Script
- Make sure you updated the deployment after changing the code
