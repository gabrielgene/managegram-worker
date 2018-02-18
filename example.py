from instapy import InstaPy


# set headless_browser=True if you want to run InstaPy on a server
try:
    insta_password = '@fabit123456'
    insta_username = 'fabitbr'
    # set these if you're locating the library in the /usr/lib/pythonX.X/ directory
    # Settings.database_location = '/path/to/instapy.db'
    # Settings.browser_location = '/path/to/chromedriver'

    session = InstaPy(username=insta_username,
                      password=insta_password,
                      headless_browser=False,
                      multi_logs=True)
    session.login()

    # settings
    session.set_upper_follower_count(limit=2500)

    # actions
    x = session.list_followers([insta_username])
    print(x)

finally:
    # end the bot session
    session.end()
