# BSD #7 Community Assistance — Full-Stack Prototype

This is a working laptop prototype of the narrow safety mission you defined.

## Run it now
Requires Python 3.10+ and no third-party packages.

### Windows
1. Extract this ZIP.
2. Open the extracted folder.
3. Double-click `start-demo.bat`, or open PowerShell in the folder and run:
   `python server.py --demo`
4. Open `http://localhost:8080` in your laptop browser.

Demo district admin:
- Email: `admin@bsd7.local`
- Password: `CommunityAssist7!`

To test as a community member, create a second account using the Create Account tab.

## Test it on your phone
Keep your laptop and phone on the same Wi-Fi.
Run `ipconfig` on Windows and find your laptop's IPv4 address. On the phone open:
`http://YOUR-LAPTOP-IP:8080`

Windows Firewall may ask to allow Python on Private networks. Allow Private-network access for this local test.

## What works in this prototype
- Community account creation and sign-in.
- District/admin role.
- Draft Community Assistance Request.
- Required investigating agency and public tip/contact number.
- Approval before an alert becomes active.
- Community alert feed.
- "I Have Information" route to the law-enforcement number.
- Immediate sighting guidance to call 911 and not approach/follow.
- Child Located / All Clear workflow.
- SQLite backend with WAL mode.
- Audit table for key actions.

## Google sign-in and real push notifications
The UI includes Google sign-in as the intended production login, but a real Google OAuth client cannot be activated until a district-approved Firebase/Google project exists. The production architecture folder explains the setup.

Real push notifications likewise require FCM/APNs credentials and a deployed backend. The alert approval endpoints in this prototype already contain the points where production push jobs would be queued.

## Production recommendation
Do not expose this local Python server to the internet. Deploy the production version on managed infrastructure such as Firebase/Google Cloud so phone crashes, laptop failures, or sudden usage spikes do not take the service down.
