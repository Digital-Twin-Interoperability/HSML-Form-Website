# HSML Web App

## File Structure

### Stylizing, Formatting


``/static/css``: Our single CSS stylesheet. Use this to modify font, background, etc. across the entire web app.

``/static/images``: Store relevant images (ex. NASA logo, our background) here, then pass the filepath as /static/images/yourImage.png in your code.

``/templates``: Each page has it's own corresponding HTML.

``/templates/index.html``: Select between Entity, Credential, and Agent, then route to relevant page.

``/templates/landing.html``: First page the user sees. Prompts to login or register.

``/templates/login.html``: Login page. Prompts to upload .pem file.

``/templates/register.html``: Prompts to create new Person or Organization object.

``/templates/result.html``:  Shows formatted JSON result, prompts user to download associated key.pem file and HSML JSON file.

``/templates/[objectType].html``: Three types: agent.html, credential.html, and entity.html. Each prompt the user for relevant fields, and then send to result.html.

### Core Logic

``app.py``: Main Python script behind the app. In reality, very simple -- just calls the API.

``.env``: Database login information (check this first for errors!)

### Troubleshooting

- Make sure you're running the API. See Alicia's guides in the main documentation repo.
- Make sure your .env information is correct.
- Errors can be with how you are formatting the message you're sending to the API -- check both the error logs for the terminal you're running the web app in AND the terminal you're running the API in.
- When in doubt, ChatGPT it out.
