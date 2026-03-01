/**
 * Google Apps Script for BenGo Email OTP
 * 
 * SETUP INSTRUCTIONS:
 * 1. Open Google Apps Script: https://script.google.com/
 * 2. Create a new project
 * 3. Replace the default Code.gs content with this file
 * 4. Deploy as Web App:
 *    - Click "Deploy" → "New deployment"
 *    - Type: "Web app"
 *    - Execute as: "Me"
 *    - Who has access: "Anyone" (required for external POST requests)
 * 5. Copy the Web App URL and set it in Django settings:
 *    APPS_SCRIPT_URL = 'your-web-app-url-here'
 * 6. Set a shared secret in Django settings:
 *    APPS_SCRIPT_SECRET = 'your-secret-here'
 * 7. Update the EXPECTED_SECRET below to match
 */

// Replace this with your shared secret (must match Django APPS_SCRIPT_SECRET)
// Current Django secret: bengo-otp-secret-2026-secure-key-xyz789
const EXPECTED_SECRET = 'bengo-otp-secret-2026-secure-key-xyz789';

// Optional: customize the sender name
const SENDER_NAME = 'BenGo';

/**
 * Handle POST requests from Django backend
 * Receives form-encoded data: email, otp, secret
 */
function doPost(e) {
  try {
    // Log for debugging (view logs in Apps Script under "Executions")
    Logger.log('Received POST request');
    Logger.log('Parameters: ' + JSON.stringify(e.parameter));
    
    // Extract form-encoded POST data
    const email = e.parameter.email;
    const otp = e.parameter.otp;
    const secret = e.parameter.secret;
    
    // Validate required fields
    if (!email || !otp) {
      return createJsonResponse({
        success: false,
        error: 'Missing required fields: email and otp'
      }, 400);
    }
    
    // Validate shared secret (recommended for security)
    if (secret !== EXPECTED_SECRET) {
      Logger.log('Invalid secret provided');
      return createJsonResponse({
        success: false,
        error: 'Unauthorized'
      }, 401);
    }
    
    // Send email via Gmail
    const subject = `${SENDER_NAME} - Email Verification Code`;
    const htmlBody = `
      <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #E60000;">BenGo Email Verification</h2>
        <p>Your verification code is:</p>
        <div style="background: #f5f5f5; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 8px; margin: 20px 0;">
          ${otp}
        </div>
        <p style="color: #666;">This code will expire in 10 minutes.</p>
        <p style="color: #666; font-size: 12px;">If you did not request this code, please ignore this email.</p>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 11px;">© 2026 BenGo - JLPT Preparation Platform</p>
      </div>
    `;
    
    const plainBody = `
BenGo Email Verification

Your verification code is: ${otp}

This code will expire in 10 minutes.

If you did not request this code, please ignore this email.

© 2026 BenGo - JLPT Preparation Platform
    `.trim();
    
    // Send the email
    GmailApp.sendEmail(email, subject, plainBody, {
      htmlBody: htmlBody,
      name: SENDER_NAME
    });
    
    Logger.log('Email sent successfully to: ' + email);
    
    // Return success response
    return createJsonResponse({
      success: true,
      message: 'OTP email sent'
    });
    
  } catch (error) {
    Logger.log('Error: ' + error.toString());
    return createJsonResponse({
      success: false,
      error: error.toString()
    }, 500);
  }
}

/**
 * Handle GET requests (for testing)
 */
function doGet(e) {
  return HtmlService.createHtmlOutput(`
    <html>
      <head>
        <title>BenGo OTP Email Service</title>
        <style>
          body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
          h1 { color: #E60000; }
          code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }
          .status { padding: 10px; background: #e8f5e9; border-left: 4px solid #4caf50; margin: 20px 0; }
        </style>
      </head>
      <body>
        <h1>BenGo OTP Email Service</h1>
        <div class="status">✓ Service is running</div>
        <p>This endpoint accepts POST requests with the following parameters:</p>
        <ul>
          <li><code>email</code> - recipient email address</li>
          <li><code>otp</code> - verification code</li>
          <li><code>secret</code> - shared secret for authentication</li>
        </ul>
        <p><strong>Web App URL:</strong></p>
        <code>${ScriptApp.getService().getUrl()}</code>
        <h3>Test with curl:</h3>
        <pre style="background: #f5f5f5; padding: 10px; overflow-x: auto;">
curl -X POST "${ScriptApp.getService().getUrl()}" \\
  -d "email=test@example.com" \\
  -d "otp=123456" \\
  -d "secret=${EXPECTED_SECRET}"
        </pre>
      </body>
    </html>
  `);
}

/**
 * Helper function to create JSON responses
 */
function createJsonResponse(data, statusCode) {
  const output = ContentService.createTextOutput(JSON.stringify(data));
  output.setMimeType(ContentService.MimeType.JSON);
  
  // Apps Script doesn't support custom status codes directly,
  // but we include them in the response body for reference
  if (statusCode && statusCode !== 200) {
    data.statusCode = statusCode;
  }
  
  return output;
}
