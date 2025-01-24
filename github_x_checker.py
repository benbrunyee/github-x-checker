import asyncio
import json
import os

from loguru import logger
from pyppeteer import launch
from pyppeteer.page import Page

logger.add("deactivated_users.log", rotation="10 MB")


class GitHubXChecker:
    def __init__(self):
        self.browser = None
        self.page = None
        self.checked_repos = set()
        self.checked_profiles = set()
        self.checked_x_accounts = set()
        self.load_checked_urls()

    def load_checked_urls(self):
        try:
            if os.path.exists("checked_urls.json"):
                with open("checked_urls.json", "r") as f:
                    data = json.load(f)
                    self.checked_repos = set(data.get("repos", []))
                    self.checked_profiles = set(data.get("profiles", []))
                    self.checked_x_accounts = set(data.get("x_accounts", []))
        except Exception as e:
            logger.error(f"Error loading checked URLs: {str(e)}")

    def save_checked_urls(self):
        try:
            with open("checked_urls.json", "w") as f:
                json.dump(
                    {
                        "repos": list(self.checked_repos),
                        "profiles": list(self.checked_profiles),
                        "x_accounts": list(self.checked_x_accounts),
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"Error saving checked URLs: {str(e)}")

    async def init_browser(self):
        # Updated browser launch options for better compatibility
        self.browser = await launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--start-maximized",
                "--window-position=0,0",
            ],
            ignoreHTTPSErrors=True,
        )
        self.page = await self.browser.newPage()

        # Set the viewport to maximum size
        await self.page.setViewport({"width": 1920, "height": 1080})

        # Set default navigation timeout
        self.page.setDefaultNavigationTimeout(30000)  # 30 seconds

        # Add user agent to avoid detection
        await self.page.setUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

    async def search_repositories(self, search_query, page=1):
        try:
            # Navigate to GitHub
            search_url = (
                f"https://github.com/search?q={search_query}&ref=advsearch&p={page}"
            )
            await self.page.goto(search_url, {"waitUntil": "networkidle0"})
            await self.check_429_error(search_url, self.page)

        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            raise

    async def check_429_error(self, url, page: Page):
        has_429 = await page.evaluate(
            "() => (document.body.textContent.includes('Error') && document.body.textContent.includes('429')) || document.body.textContent.includes('Whoa there!')"
        )
        sleep_time = 2
        counter = 0

        while has_429:
            sleep = min(sleep_time * (counter + 1), 60)
            logger.error(f"429 error returned, retrying {sleep} seconds")
            await asyncio.sleep(sleep)
            await page.goto(url, {"waitUntil": "networkidle0"})
            has_429 = await page.evaluate(
                "() => (document.body.textContent.includes('Error') && document.body.textContent.includes('429')) || document.body.textContent.includes('Whoa there!')"
            )
            counter += 1

            if counter > 10:
                logger.error("Too many 429 errors, continuing")
                return

    async def process_repository_results(self):
        while True:
            try:
                # Wait for repository items to load
                await self.page.waitForXPath(
                    "//div[contains(@class,'search-title')]//a", {"visible": True}
                )
                repo_links = await self.page.xpath(
                    "//div[contains(@class,'search-title')]//a"
                )

                for repo_link in repo_links:
                    try:
                        repo_url = await self.page.evaluate(
                            "(element) => element.href", repo_link
                        )

                        # Skip if already checked
                        if repo_url in self.checked_repos:
                            logger.info(
                                f"Skipping already checked repository: {repo_url}"
                            )
                            continue

                        self.checked_repos.add(repo_url)
                        self.save_checked_urls()

                        # Open the repo in a new tab
                        new_page = await self.browser.newPage()
                        await new_page.setUserAgent(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                        )
                        await new_page.goto(repo_url, {"waitUntil": "networkidle0"})
                        await self.check_429_error(repo_url, new_page)

                        # Wait for author link to be visible
                        await new_page.waitForSelector(
                            'a[rel="author"]', {"visible": True}
                        )
                        owner_link = await new_page.querySelector('a[rel="author"]')

                        if owner_link:
                            profile_url = await new_page.evaluate(
                                "(element) => element.href", owner_link
                            )
                            await self.check_user_profile(profile_url, repo_url)

                        await new_page.close()
                    except Exception as e:
                        logger.error(
                            f"Error processing repository {repo_url}: {str(e)}"
                        )
                        await new_page.close()
                        continue

                # Check for next page
                next_button = await self.page.querySelector("a.next_page")
                if not next_button:
                    break

                await self.page.click("a.next_page")
                await self.page.waitForNavigation({"waitUntil": "networkidle0"})
            except Exception as e:
                logger.error(f"Error during pagination: {str(e)}")
                break

    async def check_user_profile(self, profile_url, repo_url):
        try:
            # Skip if already checked
            if profile_url in self.checked_profiles:
                logger.info(f"Skipping already checked profile: {profile_url}")
                return

            self.checked_profiles.add(profile_url)
            self.save_checked_urls()

            # Open the profile in a new tab
            new_page = await self.browser.newPage()
            await new_page.setUserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            await new_page.goto(profile_url, {"waitUntil": "networkidle0"})

            social_links = await new_page.querySelectorAll(
                'a[href*="twitter.com"], a[href*="x.com"]'
            )

            for link in social_links:
                try:
                    x_url = await new_page.evaluate("(element) => element.href", link)

                    # Skip if already checked
                    if x_url in self.checked_x_accounts:
                        logger.info(f"Skipping already checked X account: {x_url}")
                        continue

                    self.checked_x_accounts.add(x_url)
                    self.save_checked_urls()

                    x_new_page = await self.browser.newPage()
                    await x_new_page.setUserAgent(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    )

                    await x_new_page.goto(x_url, {"waitUntil": "networkidle0"})

                    # Check for account status by searching entire page content
                    page_content = await x_new_page.evaluate(
                        "() => document.body.textContent"
                    )

                    if "this account doesn't exist" in page_content.lower():
                        logger.info(
                            f"Found deactivated X account for GitHub user: {profile_url} - X profile: {x_url}"
                        )
                        # Save deactivated account info to a file
                        with open(
                            "deactivated_accounts.txt", "a", encoding="utf-8"
                        ) as f:
                            f.write(
                                f"Repository: {repo_url}\nGitHub Profile: {profile_url}\nX Account: {x_url}\n\n"
                            )

                    await x_new_page.close()
                except Exception as e:
                    logger.error(f"Error checking X profile {x_url}: {str(e)}")
                    await x_new_page.close()

            await new_page.close()
        except Exception as e:
            logger.error(f"Error checking GitHub profile {profile_url}: {str(e)}")
            await new_page.close()

    async def close(self):
        if self.browser:
            response = input("\nDo you want to close the browser? (y/n): ").lower()
            if response == "y":
                await self.browser.close()
            else:
                logger.info(
                    "Browser will remain open. You can close it manually when done."
                )


async def main():
    checker = GitHubXChecker()
    try:
        await checker.init_browser()
        search_query = input("Enter your GitHub search query: ")

        page = 1

        while True:
            logger.info(f"Checking page {page}")
            await checker.search_repositories(search_query, page)
            await checker.process_repository_results()
            page += 1
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    finally:
        # Ask before closing the browser
        await checker.close()
        if checker.browser and not checker.browser.process.closed:
            logger.info("\nScript finished. Browser is still open for testing.")
            logger.info("Press Ctrl+C when you want to exit completely.")
            # Keep the script running until Ctrl+C
            while True:
                await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("\nExiting script...")
