import asyncio
import configparser
import mailslurp_client
from playwright.async_api import async_playwright


class EmailAccount:
    def __init__(self, msg: str = None):
        self.config = mailslurp_client.Configuration()
        self.config.api_key['x-api-key'] = config['MailSlurp']['api_key']
        self.subject = config['MailSlurp']['subject']
        self.body = msg
        self.send_to = config['MailSlurp']['send_to'].split(',')

    def create_inbox(self):
        with mailslurp_client.ApiClient(self.config) as api_client:
            api_instance = mailslurp_client.InboxControllerApi(api_client)
            inbox = api_instance.create_inbox()
            return inbox.email_address, inbox.id, api_instance

    def send_email(self):
        create_inbox = self.create_inbox()
        inbox_id, api_instance = create_inbox[1], create_inbox[2]

        # send email from the inbox
        send_email_options = mailslurp_client.SendEmailOptions()
        send_email_options.to = self.send_to
        send_email_options.subject = self.subject
        send_email_options.body = self.body
        send_email_options.is_html = True
        api_instance.send_email(inbox_id, send_email_options=send_email_options)


class Gousto:
    def __init__(self):
        # Config
        self.timeout = 3000
        self.url = 'https://www.gousto.co.uk/'

        # User Data
        self.userEmail = config['Gousto']['email']
        self.userPass = config['Gousto']['pw']

        # Identifiers
        self.loginBtn = '[data-testing="loginButton"]'
        self.emailField = '[data-testing="inputLoginEmail"]'
        self.emailPassField = '[data-testing="inputLoginPassword"]'
        self.confirmLoginBtn = '[data-testing="loginFormSubmit"]'
        self.upcomingDeliveries = '[data-testing="myGoustoNextBoxHelpCTA"]'
        self.pendingOrder = '[data-testing="pendingOrder"]'
        self.accountSettings = 'Subscription Settings'
        self.pauseSubscription = '[data-testing="pause-subscription-cta"]'
        self.confirmPauseSubscription = '[data-testing="continue-to-pause-link"]'
        self.prices = []
        self.email_needed = False

    async def login(self, page) -> None:
        await page.goto(self.url)
        await page.click(self.loginBtn)
        await page.fill(self.emailField, self.userEmail)
        await page.fill(self.emailPassField, self.userPass)
        await page.wait_for_timeout(self.timeout)
        await page.click(self.confirmLoginBtn)

    async def check_remaining_discount(self, page) -> None:
        await self.login(page)
        await page.click(self.upcomingDeliveries)
        await page.wait_for_selector(self.pendingOrder)

        for price_element in await page.query_selector_all(self.pendingOrder):
            order_info = await price_element.inner_text()
            price = [p.strip().replace('£', '') for p in order_info.split('\n') if '£' in p]
            if price:
                last_price = float(price[-1])
                self.prices.append(last_price)

        if any(price > 44 for price in self.prices) and not self.email_needed:
            self.email_needed = True

    async def cancel_membership(self, page) -> bool:
        await page.get_by_text(self.accountSettings).nth(1).click()
        await page.click(self.pauseSubscription)
        await page.click(self.confirmPauseSubscription)
        return True


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('config.ini')

    async def main():
        gousto = Gousto()
        email = EmailAccount()
        new_email = email.create_inbox()[0]

        email_body = f"""
        Hello!

        Your Gousto discount is expiring soon, You should create a new account.
        We have cancelled the membership for the pre existing account.

        You can use the following email to sign up for a new account if you wish:
        \nEmail: {new_email}
        \nPassword: {config['Gousto']['pw']}
        """

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            await gousto.check_remaining_discount(page)
            if gousto.email_needed:
                if await gousto.cancel_membership(page):
                    with open('config.ini', 'w') as config_file:
                        config.set('Gousto', 'email', new_email)
                        config.write(config_file)
                    EmailAccount(email_body).send_email()
            await browser.close()

    asyncio.run(main())


