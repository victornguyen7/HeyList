# HeyList — Accounts: setup

Sign up and log in use an email and a password (decision 68). Supabase Auth stores the accounts and issues the session token the backend checks (decision 52); the app never sees a password hash. Two emails are sent, both with a code rather than a link, and both from the owner's Gmail address:

| Email | When | Code checked by |
|---|---|---|
| Confirm sign up | After **Sign up**, and again on **Send a new code** or when an unconfirmed account tries to log in | `verifyOtp({ type: "signup" })` |
| Reset password | After **Forgot your password?** | `verifyOtp({ type: "recovery" })`, then the new password is saved with `updateUser` |

The screens are in `app/login/page.tsx`. Nothing in the backend changed.

## Owner setup (Supabase dashboard, once)

These are settings, not code, so they have to be done by hand. Never paste the App Password into a file, chat or issue (the same rules as [RULES.md](RULES.md)).

### 1. A Gmail App Password

1. Turn on 2-Step Verification for the Gmail account: Google Account > Security > 2-Step Verification.
2. Google Account > Security > **App passwords** (or https://myaccount.google.com/apppasswords). Create one named "HeyList Supabase". Google shows a 16-letter password once; keep it on screen for step 2.

### 2. Send from Gmail (custom SMTP)

Supabase dashboard > the HeyList project > **Authentication > Emails > SMTP Settings**, turn on **Enable custom SMTP**:

| Field | Value |
|---|---|
| Sender email | your Gmail address |
| Sender name | HeyList |
| Host | `smtp.gmail.com` |
| Port | `465` |
| Username | your Gmail address |
| Password | the App Password from step 1 |
| Minimum interval between emails | 60 seconds (the default) |

Gmail sends at most about 500 emails a day from a personal account, plenty for the hackathon. Supabase's built-in sender, used until this is on, sends only a few emails an hour.

Then **Authentication > Rate Limits**: raise "Rate limit for sending emails" (for example to 30 an hour); with custom SMTP it is editable.

### 3. Sign-up settings

**Authentication > Sign In / Providers > Email**:

- **Enable Email provider**: on.
- **Confirm email**: on (this is what sends the sign-up code).
- **Email OTP Expiration**: 3600 seconds (the emails say one hour).
- **Email OTP Length**: 6 (the page accepts 6 to 10 digits).
- **Minimum password length**: 8, to match the page.

### 4. The email templates

**Authentication > Emails > Templates**. The default templates send a link; replace them so they send the code (`{{ .Token }}`):

- **Confirm sign up**: subject `Your HeyList code: {{ .Token }}`, body from `supabase/email-templates/confirm-signup.html`.
- **Reset password**: subject `Your HeyList password reset code: {{ .Token }}`, body from `supabase/email-templates/reset-password.html`.

### 5. Try it

1. `/login` > **Sign up** with a real address you can read. The email arrives from your Gmail with a 6-digit code; enter it and you land back where you started, logged in.
2. Log out, then **Log in** with the email and password.
3. **Forgot your password?** > the code > a new password > logged in with it.

If no email arrives: check the Gmail account's **Sent** folder (if it's there, look in the recipient's spam), and the Supabase dashboard's **Logs > Auth** for an SMTP error (usually a wrong App Password).

## Accounts made with the old magic link

They keep working. They have no password, so the first time they log in that way they use **Forgot your password?** to set one.
