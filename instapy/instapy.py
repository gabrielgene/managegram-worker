"""OS Modules environ method to get the setup vars from the Environment"""
import csv
import json
import logging
import re
from math import ceil
import os
from platform import python_version
from datetime import datetime
from sys import maxsize
import random

import selenium
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver import DesiredCapabilities
from selenium.webdriver.common.proxy import Proxy, ProxyType
import requests

from .clarifai_util import check_image
from .comment_util import comment_image
from .like_util import check_link
from .like_util import get_links_for_tag
from .like_util import get_links_from_feed
from .like_util import get_tags
from .like_util import get_links_for_location
from .like_util import like_image
from .like_util import get_links_for_username
from .login_util import login_user
from .print_log_writer import log_follower_num
from .settings import Settings
from .time_util import sleep
from .time_util import set_sleep_percentage
from .util import get_active_users
from .util import validate_username
from .unfollow_util import get_given_user_followers
from .unfollow_util import get_given_user_following
from .unfollow_util import unfollow
from .unfollow_util import unfollow_user
from .unfollow_util import follow_given_user_followers
from .unfollow_util import follow_given_user_following
from .unfollow_util import follow_user
from .unfollow_util import follow_given_user
from .unfollow_util import load_follow_restriction
from .unfollow_util import dump_follow_restriction
from .unfollow_util import set_automated_followed_pool
from .unfollow_util import get_list_followers


# Set a logger cache outside the InstaPy object to avoid re-instantiation issues
loggers = {}


class InstaPyError(Exception):
    """General error for InstaPy exceptions"""


class InstaPy:
    """Class to be instantiated to use the script"""

    def __init__(self,
                 username=None,
                 password=None,
                 nogui=False,
                 selenium_local_session=True,
                 use_firefox=False,
                 page_delay=25,
                 show_logs=True,
                 headless_browser=False,
                 proxy_address=None,
                 proxy_chrome_extension=None,
                 proxy_port=0,
                 bypass_suspicious_attempt=False,
                 multi_logs=False):

        if nogui:
            self.display = Display(visible=0, size=(800, 600))
            self.display.start()

        self.browser = None
        self.headless_browser = headless_browser
        self.proxy_address = proxy_address
        self.proxy_port = proxy_port
        self.proxy_chrome_extension = proxy_chrome_extension

        self.username = username or os.environ.get('INSTA_USER')
        self.password = password or os.environ.get('INSTA_PW')
        self.nogui = nogui
        self.logfolder = Settings.log_location + os.path.sep
        if multi_logs is True:
            self.logfolder = '{0}{1}{2}{1}'.format(
                Settings.log_location, os.path.sep, self.username)
        if not os.path.exists(self.logfolder):
            os.makedirs(self.logfolder)

        self.page_delay = page_delay
        self.switch_language = True
        self.use_firefox = use_firefox
        self.firefox_profile_path = None

        self.do_comment = False
        self.comment_percentage = 0
        self.comments = ['Cool!', 'Nice!', 'Looks good!']
        self.photo_comments = []
        self.video_comments = []

        self.followed = 0
        self.liked_img = 0
        self.already_liked = 0
        self.inap_img = 0
        self.commented = 0
        self.followed_by = 0
        self.unfollowNumber = 0

        self.follow_restrict = load_follow_restriction(self.logfolder)
        self.follow_times = 1
        self.do_follow = False
        self.follow_percentage = 0
        self.dont_include = []
        self.blacklist = {'enabled': 'True', 'campaign': ''}
        self.automatedFollowedPool = []
        self.do_like = False
        self.like_percentage = 0
        self.smart_hashtags = []

        self.dont_like = ['sex', 'nsfw']
        self.ignore_if_contains = []
        self.ignore_users = []

        self.user_interact_amount = 0
        self.user_interact_media = None
        self.user_interact_percentage = 0
        self.user_interact_random = False

        self.use_clarifai = False
        self.clarifai_api_key = None
        self.clarifai_img_tags = []
        self.clarifai_full_match = False

        self.like_by_followers_upper_limit = 90000
        self.like_by_followers_lower_limit = 0

        self.bypass_suspicious_attempt = bypass_suspicious_attempt

        self.aborting = False

        # Assign logger
        self.logger = self.get_instapy_logger(show_logs)

        if selenium_local_session:
            self.set_selenium_local_session()

        if os.name == 'nt':
            error_msg = ('Sorry, Record Activity is not working on Windows. '
                         'We\'re working to fix this soon!')
            self.logger.warning(error_msg)

    def get_instapy_logger(self, show_logs):
        """
        Handles the creation and retrieval of loggers to avoid re-instantiation.
        """
        existing_logger = loggers.get(__name__)
        if existing_logger is not None:
            return existing_logger
        else:
            # initialize and setup logging system for the InstaPy object
            logger = logging.getLogger(__name__)
            logger.setLevel(logging.DEBUG)
            file_handler = logging.FileHandler('{}general.log'.format(self.logfolder))
            file_handler.setLevel(logging.DEBUG)
            extra = {"username": self.username}
            logger_formatter = logging.Formatter('%(levelname)s [%(asctime)s] [%(username)s]  %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(logger_formatter)
            logger.addHandler(file_handler)

            if show_logs is True:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.DEBUG)
                console_handler.setFormatter(logger_formatter)
                logger.addHandler(console_handler)

            logger = logging.LoggerAdapter(logger, extra)

            loggers[__name__] = logger
            return logger

    def set_selenium_local_session(self):
        """Starts local session for a selenium server.
        Default case scenario."""
        if self.aborting:
            return self

        if self.use_firefox:
            if self.firefox_profile_path is not None:
                firefox_profile = webdriver.FirefoxProfile(
                    self.firefox_profile_path)
            else:
                firefox_profile = webdriver.FirefoxProfile()

            # permissions.default.image = 2: Disable images load,
            # this setting can improve pageload & save bandwidth
            firefox_profile.set_preference('permissions.default.image', 2)

            if self.proxy_address and self.proxy_port > 0:
                firefox_profile.set_preference('network.proxy.type', 1)
                firefox_profile.set_preference('network.proxy.http',
                                               self.proxy_address)
                firefox_profile.set_preference('network.proxy.http_port',
                                               self.proxy_port)
                firefox_profile.set_preference('network.proxy.ssl',
                                               self.proxy_address)
                firefox_profile.set_preference('network.proxy.ssl_port',
                                               self.proxy_port)

            self.browser = webdriver.Firefox(firefox_profile=firefox_profile)

        else:
            chromedriver_location = Settings.chromedriver_location
            chrome_options = Options()
            chrome_options.add_argument('--dns-prefetch-disable')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--lang=en-US')
            chrome_options.add_argument('--disable-setuid-sandbox')

            # this option implements Chrome Headless, a new (late 2017)
            # GUI-less browser. chromedriver 2.9 and above required
            if self.headless_browser:
                chrome_options.add_argument('--headless')
                # Replaces browser User Agent from "HeadlessChrome".
                user_agent = "Chrome"
                chrome_options.add_argument('user-agent={user_agent}'
                                            .format(user_agent=user_agent))
            capabilities = DesiredCapabilities.CHROME
            # Proxy for chrome
            if self.proxy_address and self.proxy_port > 0:
                prox = Proxy()
                proxy = ":".join([self.proxy_address, str(self.proxy_port)])
                prox.proxy_type = ProxyType.MANUAL
                prox.http_proxy = proxy
                prox.socks_proxy = proxy
                prox.ssl_proxy = proxy
                prox.add_to_capabilities(capabilities)

            # add proxy extension
            if self.proxy_chrome_extension and not self.headless_browser:
                chrome_options.add_extension(self.proxy_chrome_extension)

            chrome_prefs = {
                'intl.accept_languages': 'en-US'
            }
            chrome_options.add_experimental_option('prefs', chrome_prefs)
            try:
                self.browser = webdriver.Chrome(chromedriver_location,
                                                desired_capabilities=capabilities,
                                                chrome_options=chrome_options)
            except selenium.common.exceptions.WebDriverException as exc:
                self.logger.exception(exc)
                raise InstaPyError('ensure chromedriver is installed at {}'.format(
                    Settings.chromedriver_location))

            # prevent: Message: unknown error: call function result missing 'value'
            matches = re.match(r'^(\d+\.\d+)',
                               self.browser.capabilities['chrome']['chromedriverVersion'])
            if float(matches.groups()[0]) < Settings.chromedriver_min_version:
                raise InstaPyError('chromedriver {} is not supported, expects {}+'.format(
                    float(matches.groups()[0]), Settings.chromedriver_min_version))

        self.browser.implicitly_wait(self.page_delay)
        self.logger.info('Session started - %s'
                         % (datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        return self

    def set_selenium_remote_session(self, selenium_url=''):
        """Starts remote session for a selenium server.
         Useful for docker setup."""
        if self.aborting:
            return self

        if self.use_firefox:
            self.browser = webdriver.Remote(
                command_executor=selenium_url,
                desired_capabilities=DesiredCapabilities.FIREFOX)
        else:
            self.browser = webdriver.Remote(
                command_executor=selenium_url,
                desired_capabilities=DesiredCapabilities.CHROME)

        self.logger.info('Session started - %s'
                         % (datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        return self

    def login(self):
        """Used to login the user either with the username and password"""
        if not login_user(self.browser,
                          self.username,
                          self.password,
                          self.logfolder,
                          self.switch_language,
                          self.bypass_suspicious_attempt):
            self.logger.critical('Wrong login data!')

            self.aborting = True
        else:
            self.logger.info('Logged in successfully!')

        self.followed_by = log_follower_num(self.browser, self.username, self.logfolder)

        return self

    def set_sleep_reduce(self, percentage):
        set_sleep_percentage(percentage)

        return self

    def set_do_comment(self, enabled=False, percentage=0):
        """Defines if images should be commented or not
        percentage=25 -> ~ every 4th picture will be commented"""
        if self.aborting:
            return self

        self.do_comment = enabled
        self.comment_percentage = percentage

        return self

    def set_comments(self, comments=None, media=None):
        """Changes the possible comments"""
        if self.aborting:
            return self

        if (media not in [None, 'Photo', 'Video']):
            self.logger.warning('Unkown media type! Treating as "any".')
            media = None

        self.comments = comments or []

        if media is None:
            self.comments = comments
        else:
            attr = '{}_comments'.format(media.lower())
            setattr(self, attr, comments)

        return self

    def set_do_follow(self, enabled=False, percentage=0, times=1):
        """Defines if the user of the liked image should be followed"""
        if self.aborting:
            return self

        self.follow_times = times
        self.do_follow = enabled
        self.follow_percentage = percentage

        return self

    def set_do_like(self, enabled=False, percentage=0):
        if self.aborting:
            return self

        self.do_like = enabled
        self.like_percentage = percentage

        return self

    def set_dont_like(self, tags=None):
        """Changes the possible restriction tags, if one of this
         words is in the description, the image won't be liked"""
        if self.aborting:
            return self

        if not isinstance(tags, list):
            self.logger.warning('Unable to use your set_dont_like '
                                'configuration!')
            self.aborting = True

        self.dont_like = tags or []

        return self

    def set_user_interact(self,
                          amount=10,
                          percentage=100,
                          randomize=False,
                          media=None):
        """Define if posts of given user should be interacted"""
        if self.aborting:
            return self

        self.user_interact_amount = amount
        self.user_interact_random = randomize
        self.user_interact_percentage = percentage
        self.user_interact_media = media

        return self

    def set_ignore_users(self, users=None):
        """Changes the possible restriction to users, if user who postes
        is one of this, the image won't be liked"""
        if self.aborting:
            return self

        self.ignore_users = users or []

        return self

    def set_ignore_if_contains(self, words=None):
        """ignores the don't likes if the description contains
        one of the given words"""
        if self.aborting:
            return self

        self.ignore_if_contains = words or []

        return self

    def set_dont_include(self, friends=None):
        """Defines which accounts should not be unfollowed"""
        if self.aborting:
            return self

        self.dont_include = friends or []

        return self

    def set_switch_language(self, option=True):
        self.switch_language = option
        return self

    def set_use_clarifai(self, enabled=False, api_key=None, full_match=False):
        """
        Defines if the clarifai img api should be used
        Which 'project' will be used (only 5000 calls per month)

        Raises:
            InstaPyError if os is windows
        """
        if self.aborting:
            return self

        if os.name == 'nt':
            raise InstaPyError('Clarifai is not supported on Windows')

        self.use_clarifai = enabled

        if api_key is None and self.clarifai_api_key is None:
            self.clarifai_api_key = os.environ.get('CLARIFAI_API_KEY')
        elif api_key is not None:
            self.clarifai_api_key = api_key

        self.clarifai_full_match = full_match

        return self

    def set_smart_hashtags(self,
                           tags=None,
                           limit=3,
                           sort='top',
                           log_tags=True):
        """Generate smart hashtags based on https://displaypurposes.com/"""
        """ranking, banned and spammy tags are filtered out."""

        if tags is None:
            print('set_smart_hashtags is misconfigured')
            return

        for tag in tags:
            req = requests.get(
                u'https://d212rkvo8t62el.cloudfront.net/tag/{}'.format(tag))
            data = json.loads(req.text)

            if data['tagExists'] is True:
                if sort == 'top':
                    # sort by ranking
                    ordered_tags_by_rank = sorted(
                        data['results'], key=lambda d: d['rank'], reverse=True)
                    ranked_tags = (ordered_tags_by_rank[:limit])
                    for item in ranked_tags:
                        # add smart hashtag to like list
                        self.smart_hashtags.append(item['tag'])

                elif sort == 'random':
                    random_tags = random.sample(data['results'], limit)
                    for item in random_tags:
                        self.smart_hashtags.append(item['tag'])

                if log_tags is True:
                    for item in self.smart_hashtags:
                        print(u'[smart hashtag generated: {}]'.format(item))
            else:
                print('Too few results for #{} tag'.format(tag))

        # delete duplicated tags
        self.smart_hashtags = list(set(self.smart_hashtags))
        return self

    def clarifai_check_img_for(self, tags=None, comment=False, comments=None):
        """Defines the tags, the images should be checked for"""
        if self.aborting:
            return self

        if tags is None and not self.clarifai_img_tags:
            self.use_clarifai = False
        elif tags:
            self.clarifai_img_tags.append((tags, comment, comments))

        return self

    def follow_by_list(self, followlist, times=1):
        """Allows to follow by any scrapped list"""
        self.follow_times = times or 0
        if self.aborting:
            return self

        followed = 0

        for acc_to_follow in followlist:
            if acc_to_follow in self.dont_include:
                continue

            if self.follow_restrict.get(acc_to_follow, 0) < self.follow_times:
                followed += follow_given_user(self.browser,
                                              self.username,
                                              acc_to_follow,
                                              self.follow_restrict,
                                              self.blacklist,
                                              self.logger,
                                              self.logfolder)
                self.followed += followed
                self.logger.info('Followed: {}'.format(str(followed)))
                followed = 0
            else:
                self.logger.info('---> {} has already been followed more than '
                                 '{} times'.format(
                                    acc_to_follow, str(self.follow_times)))
                sleep(1)

        return self

    def set_upper_follower_count(self, limit=None):
        """Used to chose if a post is liked by the number of likes"""
        self.like_by_followers_upper_limit = limit or maxsize
        return self

    def set_lower_follower_count(self, limit=None):
        """Used to chose if a post is liked by the number of likes"""
        self.like_by_followers_lower_limit = limit or 0
        return self

    def like_by_locations(self,
                          locations=None,
                          amount=50,
                          media=None,
                          skip_top_posts=True):
        """Likes (default) 50 images per given locations"""
        if self.aborting:
            return self

        liked_img = 0
        already_liked = 0
        inap_img = 0
        commented = 0
        followed = 0

        locations = locations or []

        for index, location in enumerate(locations):
            self.logger.info('Location [{}/{}]'
                             .format(index + 1, len(locations)))
            self.logger.info('--> {}'.format(location.encode('utf-8')))

            try:
                links = get_links_for_location(self.browser,
                                               location,
                                               amount,
                                               self.logger,
                                               media,
                                               skip_top_posts)
            except NoSuchElementException:
                self.logger.warning('Too few images, skipping this location')
                continue

            for i, link in enumerate(links):
                self.logger.info('[{}/{}]'.format(i + 1, len(links)))
                self.logger.info(link)

                try:
                    inappropriate, user_name, is_video, reason = (
                        check_link(self.browser,
                                   link,
                                   self.dont_like,
                                   self.ignore_if_contains,
                                   self.ignore_users,
                                   self.username,
                                   self.like_by_followers_upper_limit,
                                   self.like_by_followers_lower_limit,
                                   self.logger)
                    )

                    if not inappropriate:
                        liked = like_image(self.browser,
                                           user_name,
                                           self.blacklist,
                                           self.logger,
                                           self.logfolder)

                        if liked:
                            liked_img += 1
                            checked_img = True
                            temp_comments = []
                            commenting = random.randint(
                                0, 100) <= self.comment_percentage
                            following = random.randint(
                                0, 100) <= self.follow_percentage

                            if self.use_clarifai and (following or commenting):
                                try:
                                    checked_img, temp_comments = (
                                        check_image(self.browser,
                                                    self.clarifai_api_key,
                                                    self.clarifai_img_tags,
                                                    self.logger,
                                                    self.clarifai_full_match)
                                    )
                                except Exception as err:
                                    self.logger.error(
                                        'Image check error: {}'.format(err))

                            if (self.do_comment and
                                user_name not in self.dont_include and
                                checked_img and
                                    commenting):

                                if temp_comments:
                                    # Use clarifai related comments only!
                                    comments = temp_comments
                                elif is_video:
                                    comments = (self.comments +
                                                self.video_comments)
                                else:
                                    comments = (self.comments +
                                                self.photo_comments)
                                commented += comment_image(self.browser,
                                                           user_name,
                                                           comments,
                                                           self.blacklist,
                                                           self.logger,
                                                           self.logfolder)
                            else:
                                self.logger.info('--> Not commented')
                                sleep(1)

                            if (self.do_follow and
                                user_name not in self.dont_include and
                                checked_img and
                                following and
                                self.follow_restrict.get(user_name, 0) <
                                    self.follow_times):

                                followed += follow_user(self.browser,
                                                        self.follow_restrict,
                                                        self.username,
                                                        user_name,
                                                        self.blacklist,
                                                        self.logger,
                                                        self.logfolder)

                            else:
                                self.logger.info('--> Not following')
                                sleep(1)
                        else:
                            already_liked += 1
                    else:
                        self.logger.info(
                            '--> Image not liked: {}'.format(reason))
                        inap_img += 1
                except NoSuchElementException as err:
                    self.logger.error('Invalid Page: {}'.format(err))

        self.logger.info('Liked: {}'.format(liked_img))
        self.logger.info('Already Liked: {}'.format(already_liked))
        self.logger.info('Inappropriate: {}'.format(inap_img))
        self.logger.info('Commented: {}'.format(commented))
        self.logger.info('Followed: {}'.format(followed))

        self.followed += followed
        self.liked_img += liked_img
        self.already_liked += already_liked
        self.inap_img += inap_img
        self.commented += commented

        return self

    def comment_by_locations(self,
                      locations=None,
                      amount=50,
                      media=None,
                      skip_top_posts=True):
        """Likes (default) 50 images per given locations"""
        if self.aborting:
            return self

        liked_img = 0
        already_liked = 0
        inap_img = 0
        commented = 0
        followed = 0

        locations = locations or []

        for index, location in enumerate(locations):
            self.logger.info('Location [{}/{}]'
                             .format(index + 1, len(locations)))
            self.logger.info('--> {}'.format(location.encode('utf-8')))

            try:
                links = get_links_for_location(self.browser,
                                               location,
                                               amount,
                                               self.logger,
                                               media,
                                               skip_top_posts)
            except NoSuchElementException:
                self.logger.warning('Too few images, skipping this location')
                continue

            for i, link in enumerate(links):
                self.logger.info('[{}/{}]'.format(i + 1, len(links)))
                self.logger.info(link)

                try:
                    inappropriate, user_name, is_video, reason = (
                        check_link(self.browser,
                                   link,
                                   self.dont_like,
                                   self.ignore_if_contains,
                                   self.ignore_users,
                                   self.username,
                                   self.like_by_followers_upper_limit,
                                   self.like_by_followers_lower_limit,
                                   self.logger)
                    )

                    if not inappropriate:
                        liked = True

                        self.logger.info('--> Image not liked: Likes are disabled for method \'comment_by_locations\'')

                        if liked:
                            liked_img += 1
                            checked_img = True
                            temp_comments = []
                            commenting = random.randint(
                                0, 100) <= self.comment_percentage
                            following = random.randint(
                                0, 100) <= self.follow_percentage

                            if self.use_clarifai and (following or commenting):
                                try:
                                    checked_img, temp_comments = (
                                        check_image(self.browser,
                                                    self.clarifai_api_key,
                                                    self.clarifai_img_tags,
                                                    self.logger,
                                                    self.clarifai_full_match)
                                    )
                                except Exception as err:
                                    self.logger.error(
                                        'Image check error: {}'.format(err))

                            if (self.do_comment and
                                user_name not in self.dont_include and
                                checked_img and
                                    commenting):

                                if temp_comments:
                                    # Use clarifai related comments only!
                                    comments = temp_comments
                                elif is_video:
                                    comments = (self.comments +
                                                self.video_comments)
                                else:
                                    comments = (self.comments +
                                                self.photo_comments)
                                commented += comment_image(self.browser,
                                                           user_name,
                                                           comments,
                                                           self.blacklist,
                                                           self.logger,
                                                           self.logfolder)
                            else:
                                self.logger.info('--> Not commented')
                                sleep(1)

                            if (self.do_follow and
                                user_name not in self.dont_include and
                                checked_img and
                                following and
                                self.follow_restrict.get(user_name, 0) <
                                    self.follow_times):

                                followed += follow_user(self.browser,
                                                        self.follow_restrict,
                                                        self.username,
                                                        user_name,
                                                        self.blacklist,
                                                        self.logger,
                                                        self.logfolder)

                            else:
                                self.logger.info('--> Not following')
                                sleep(1)
                        else:
                            already_liked += 1
                    else:
                        self.logger.info(
                            '--> Image not liked: {}'.format(reason.encode('utf-8')))
                        inap_img += 1
                except NoSuchElementException as err:
                    self.logger.error('Invalid Page: {}'.format(err))

        self.logger.info('Liked: {}'.format(liked_img))
        self.logger.info('Already Liked: {}'.format(already_liked))
        self.logger.info('Inappropriate: {}'.format(inap_img))
        self.logger.info('Commented: {}'.format(commented))
        self.logger.info('Followed: {}'.format(followed))

        self.followed += followed

        return self

    def like_by_tags(self,
                     tags=None,
                     amount=50,
                     media=None,
                     skip_top_posts=True,
                     use_smart_hashtags=False,
                     interact=False):
        """Likes (default) 50 images per given tag"""
        if self.aborting:
            return self

        liked_img = 0
        already_liked = 0
        inap_img = 0
        commented = 0
        followed = 0

        # if smart hashtag is enabled
        if use_smart_hashtags is True and self.smart_hashtags is not []:
            print('Using smart hashtags')
            tags = self.smart_hashtags

        # deletes white spaces in tags
        tags = [tag.strip() for tag in tags]

        tags = tags or []

        for index, tag in enumerate(tags):
            self.logger.info('Tag [{}/{}]'.format(index + 1, len(tags)))
            self.logger.info('--> {}'.format(tag.encode('utf-8')))

            try:
                links = get_links_for_tag(self.browser,
                                          tag,
                                          amount,
                                          self.logger,
                                          media,
                                          skip_top_posts)
            except NoSuchElementException:
                self.logger.error('Too few images, skipping this tag')
                continue

            for i, link in enumerate(links):
                self.logger.info('[{}/{}]'.format(i + 1, len(links)))
                self.logger.info(link)

                try:
                    inappropriate, user_name, is_video, reason = (
                        check_link(self.browser,
                                   link,
                                   self.dont_like,
                                   self.ignore_if_contains,
                                   self.ignore_users,
                                   self.username,
                                   self.like_by_followers_upper_limit,
                                   self.like_by_followers_lower_limit,
                                   self.logger)
                    )

                    if not inappropriate:
                        liked = like_image(self.browser,
                                           user_name,
                                           self.blacklist,
                                           self.logger,
                                           self.logfolder)

                        if liked:

                            if interact:
                                username = (self.browser.
                                    find_element_by_xpath(
                                        '//article/header/div[2]/'
                                        'div[1]/div/a'))

                                username = username.get_attribute("title")
                                name = []
                                name.append(username)

                                self.logger.info(
                                    '--> User followed: {}'
                                    .format(name))
                                self.like_by_users(
                                    name,
                                    self.user_interact_amount,
                                    self.user_interact_random,
                                    self.user_interact_media)

                            liked_img += 1
                            checked_img = True
                            temp_comments = []
                            commenting = (random.randint(0, 100) <=
                                          self.comment_percentage)
                            following = (random.randint(0, 100) <=
                                         self.follow_percentage)

                            if self.use_clarifai and (following or commenting):
                                try:
                                    checked_img, temp_comments = (
                                        check_image(self.browser,
                                                    self.clarifai_api_key,
                                                    self.clarifai_img_tags,
                                                    self.logger,
                                                    self.clarifai_full_match)
                                    )
                                except Exception as err:
                                    self.logger.error(
                                        'Image check error: {}'.format(err))

                            if (self.do_comment and
                                user_name not in self.dont_include and
                                checked_img and
                                    commenting):

                                if temp_comments:
                                    # Use clarifai related comments only!
                                    comments = temp_comments
                                elif is_video:
                                    comments = (self.comments +
                                                self.video_comments)
                                else:
                                    comments = (self.comments +
                                                self.photo_comments)
                                commented += comment_image(self.browser,
                                                           user_name,
                                                           comments,
                                                           self.blacklist,
                                                           self.logger,
                                                           self.logfolder)
                            else:
                                self.logger.info('--> Not commented')
                                sleep(1)

                            if (self.do_follow and
                                user_name not in self.dont_include and
                                checked_img and
                                following and
                                self.follow_restrict.get(user_name, 0) <
                                    self.follow_times):

                                followed += follow_user(self.browser,
                                                        self.follow_restrict,
                                                        self.username,
                                                        user_name,
                                                        self.blacklist,
                                                        self.logger,
                                                        self.logfolder)
                            else:
                                self.logger.info('--> Not following')
                                sleep(1)
                        else:
                            already_liked += 1
                    else:
                        self.logger.info(
                            '--> Image not liked: {}'.format(reason.encode('utf-8')))
                        inap_img += 1
                except NoSuchElementException as err:
                    self.logger.error('Invalid Page: {}'.format(err))

        self.logger.info('Liked: {}'.format(liked_img))
        self.logger.info('Already Liked: {}'.format(already_liked))
        self.logger.info('Inappropriate: {}'.format(inap_img))
        self.logger.info('Commented: {}'.format(commented))
        self.logger.info('Followed: {}'.format(followed))

        self.followed += followed
        self.liked_img += liked_img
        self.already_liked += already_liked
        self.inap_img += inap_img
        self.commented += commented

        return self

    def like_by_users(self, usernames, amount=10, randomize=False, media=None):
        """Likes some amounts of images for each usernames"""
        if self.aborting:
            return self

        liked_img = 0
        total_liked_img = 0
        already_liked = 0
        inap_img = 0
        commented = 0
        followed = 0
        usernames = usernames or []

        for index, username in enumerate(usernames):
            self.logger.info(
                'Username [{}/{}]'.format(index + 1, len(usernames)))
            self.logger.info('--> {}'.format(username.encode('utf-8')))
            following = random.randint(0, 100) <= self.follow_percentage

            valid_user = validate_username(self.browser,
                                           username,
                                           self.ignore_users,
                                           self.blacklist,
                                           self.like_by_followers_upper_limit,
                                           self.like_by_followers_lower_limit)
            if valid_user is not True:
                self.logger.info(valid_user)
                continue

            try:
                links = get_links_for_username(
                    self.browser,
                    username,
                    amount,
                    self.logger,
                    randomize,
                    media)
            except NoSuchElementException:
                self.logger.error('Element not found, skipping this username')
                continue

            if (self.do_follow and
                username not in self.dont_include and
                following and
                    self.follow_restrict.get(username, 0) < self.follow_times):
                followed += follow_user(self.browser,
                                        self.follow_restrict,
                                        self.username,
                                        username,
                                        self.blacklist,
                                        self.logger,
                                        self.logfolder)
            else:
                self.logger.info('--> Not following')
                sleep(1)

            if links is False:
                continue

            # Reset like counter for every username
            liked_img = 0

            for i, link in enumerate(links):
                # Check if target has reached
                if liked_img >= amount:
                    self.logger.info('-------------')
                    self.logger.info("--> Total liked image reached it's "
                                     "amount given: {}".format(liked_img))
                    break

                self.logger.info('Post [{}/{}]'.format(liked_img + 1, amount))
                self.logger.info(link)

                try:
                    inappropriate, user_name, is_video, reason = (
                        check_link(self.browser,
                                   link,
                                   self.dont_like,
                                   self.ignore_if_contains,
                                   self.ignore_users,
                                   self.username,
                                   self.like_by_followers_upper_limit,
                                   self.like_by_followers_lower_limit,
                                   self.logger)
                    )

                    if not inappropriate:
                        liked = like_image(self.browser,
                                           user_name,
                                           self.blacklist,
                                           self.logger,
                                           self.logfolder)

                        if liked:
                            total_liked_img += 1
                            liked_img += 1
                            checked_img = True
                            temp_comments = []
                            commenting = random.randint(
                                0, 100) <= self.comment_percentage

                            if self.use_clarifai and (following or commenting):
                                try:
                                    checked_img, temp_comments = (
                                        check_image(self.browser,
                                                    self.clarifai_api_key,
                                                    self.clarifai_img_tags,
                                                    self.logger,
                                                    self.clarifai_full_match)
                                    )
                                except Exception as err:
                                    self.logger.error(
                                        'Image check error: {}'.format(err))
                            if (self.do_comment and
                                user_name not in self.dont_include and
                                checked_img and
                                    commenting):

                                if temp_comments:
                                    # use clarifai related comments only!
                                    comments = temp_comments
                                elif is_video:
                                    comments = (self.comments +
                                                self.video_comments)
                                else:
                                    comments = (self.comments +
                                                self.photo_comments)
                                commented += comment_image(self.browser,
                                                           user_name,
                                                           comments,
                                                           self.blacklist,
                                                           self.logger,
                                                           self.logfolder)
                            else:
                                self.logger.info('--> Not commented')
                                sleep(1)

                        else:
                            already_liked += 1

                    else:
                        self.logger.info(
                            '--> Image not liked: {}'.format(reason.encode('utf-8')))
                        inap_img += 1
                except NoSuchElementException as err:
                    self.logger.error('Invalid Page: {}'.format(err))

            if liked_img < amount:
                self.logger.info('-------------')
                self.logger.info("--> Given amount not fullfilled, "
                                 "image pool reached its end\n")

        self.logger.info('Liked: {}'.format(total_liked_img))
        self.logger.info('Already Liked: {}'.format(already_liked))
        self.logger.info('Inappropriate: {}'.format(inap_img))
        self.logger.info('Commented: {}'.format(commented))

        self.liked_img += liked_img
        self.already_liked += already_liked
        self.inap_img += inap_img
        self.commented += commented

        return self

    def interact_by_users(self,
                          usernames,
                          amount=10,
                          randomize=False,
                          media=None):
        """Likes some amounts of images for each usernames"""
        if self.aborting:
            return self

        total_liked_img = 0
        already_liked = 0
        inap_img = 0
        commented = 0
        followed = 0

        usernames = usernames or []

        for index, username in enumerate(usernames):
            self.logger.info(
                'Username [{}/{}]'.format(index + 1, len(usernames)))
            self.logger.info('--> {}'.format(username.encode('utf-8')))

            try:
                links = get_links_for_username(self.browser,
                                               username,
                                               amount,
                                               self.logger,
                                               randomize,
                                               media)
            except NoSuchElementException:
                self.logger.error('Element not found, skipping this username')
                continue

            if links is False:
                continue

            # Reset like counter for every username
            liked_img = 0

            # Will we follow this user?
            following = random.randint(0, 100) <= self.follow_percentage

            for i, link in enumerate(links):
                # Check if target has reached
                if liked_img >= amount:
                    self.logger.info('-------------')
                    self.logger.info("--> Total liked image reached it's "
                                     "amount given: {}".format(liked_img))
                    break

                self.logger.info('Post [{}/{}]'.format(liked_img + 1, amount))
                self.logger.info(link)

                try:
                    inappropriate, user_name, is_video, reason = (
                        check_link(self.browser,
                                   link,
                                   self.dont_like,
                                   self.ignore_if_contains,
                                   self.ignore_users,
                                   self.username,
                                   self.like_by_followers_upper_limit,
                                   self.like_by_followers_lower_limit,
                                   self.logger)
                    )

                    if not inappropriate:

                        if (self.do_follow and
                            username not in self.dont_include and
                            following and
                            self.follow_restrict.get(
                                username, 0) < self.follow_times):

                            followed += follow_user(
                                self.browser,
                                self.follow_restrict,
                                self.username,
                                username,
                                self.blacklist,
                                self.logger,
                                self.logfolder)

                            following = False
                        else:
                            self.logger.info('--> Not following')
                            sleep(1)

                        liking = random.randint(0, 100) <= self.like_percentage
                        if self.do_like and liking:
                            liked = like_image(self.browser,
                                               user_name,
                                               self.blacklist,
                                               self.logger,
                                               self.logfolder)
                        else:
                            liked = True

                        if liked:
                            total_liked_img += 1
                            liked_img += 1
                            checked_img = True
                            temp_comments = []
                            commenting = random.randint(
                                0, 100) <= self.comment_percentage

                            if self.use_clarifai and (following or commenting):
                                try:
                                    checked_img, temp_comments = (
                                        check_image(self.browser,
                                                    self.clarifai_api_key,
                                                    self.clarifai_img_tags,
                                                    self.logger,
                                                    self.clarifai_full_match)
                                    )
                                except Exception as err:
                                    self.logger.error(
                                        'Image check error: {}'.format(err))
                            if (self.do_comment and
                                user_name not in self.dont_include and
                                checked_img and
                                    commenting):

                                if temp_comments:
                                    # use clarifai related comments only!
                                    comments = temp_comments
                                elif is_video:
                                    comments = (self.comments +
                                                self.video_comments)
                                else:
                                    comments = (self.comments +
                                                self.photo_comments)
                                commented += comment_image(self.browser,
                                                           user_name,
                                                           comments,
                                                           self.blacklist,
                                                           self.logger,
                                                           self.logfolder)
                            else:
                                self.logger.info('--> Not commented')
                                sleep(1)
                        else:
                            already_liked += 1

                    else:
                        self.logger.info(
                            '--> Image not liked: {}'.format(reason.encode('utf-8')))
                        inap_img += 1
                except NoSuchElementException as err:
                    self.logger.info('Invalid Page: {}'.format(err))

            if liked_img < amount:
                self.logger.info('-------------')
                self.logger.info("--> Given amount not fullfilled, image pool "
                                 "reached its end\n")

        self.logger.info('Liked: {}'.format(total_liked_img))
        self.logger.info('Already Liked: {}'.format(already_liked))
        self.logger.info('Inappropriate: {}'.format(inap_img))
        self.logger.info('Commented: {}'.format(commented))

        self.liked_img += total_liked_img
        self.already_liked += already_liked
        self.inap_img += inap_img
        self.commented += commented

        return self

    def like_from_image(self, url, amount=50, media=None):
        """Gets the tags from an image and likes 50 images for each tag"""
        if self.aborting:
            return self

        try:
            if not url:
                urls = self.browser.find_elements_by_xpath(
                    "//main//article//div//div[1]//div[1]//a[1]")
                url = urls[0].get_attribute("href")
                self.logger.info("new url {}".format(url))
            tags = get_tags(self.browser, url)
            self.logger.info(tags)
            self.like_by_tags(tags, amount, media)
        except TypeError as err:
            self.logger.error('Sorry, an error occured: {}'.format(err))
            self.aborting = True
            return self

        return self

    def interact_user_followers(self, usernames, amount=10, randomize=False):

        userToInteract = []
        if not isinstance(usernames, list):
            usernames = [usernames]
        try:
            for user in usernames:

                user = get_given_user_followers(self.browser,
                                                user,
                                                amount,
                                                self.dont_include,
                                                self.username,
                                                randomize,
                                                self.logger)
                if isinstance(user, list):
                    userToInteract += user
        except (TypeError, RuntimeWarning) as err:
            if isinstance(err, RuntimeWarning):
                self.logger.warning(
                    u'Warning: {} , stopping follow_users'.format(err))
                return self
            else:
                self.logger.error('Sorry, an error occured: {}'.format(err))
                self.aborting = True
                return self

        self.logger.info('--> Users: {} \n'.format(len(userToInteract)))
        userToInteract = random.sample(
            userToInteract,
            int(ceil(
                self.user_interact_percentage * len(userToInteract) / 100)))

        self.like_by_users(userToInteract,
                           self.user_interact_amount,
                           self.user_interact_random,
                           self.user_interact_media)

        return self

    def list_followers(self,
                              usernames,
                              amount=10,
                              randomize=False,
                              interact=False,
                              sleep_delay=600):

        userFollowed = []
        if not isinstance(usernames, list):
            usernames = [usernames]
        for user in usernames:

            try:
                followers_list = get_list_followers(self.browser,
                                                            user,
                                                            amount,
                                                            self.dont_include,
                                                            self.username,
                                                            self.follow_restrict,
                                                            randomize,
                                                            sleep_delay,
                                                            self.blacklist,
                                                            self.logger,
                                                            self.logfolder,
                                                            self.follow_times)

            except (TypeError, RuntimeWarning) as err:
                if isinstance(err, RuntimeWarning):
                    self.logger.warning(
                        u'Warning: {} , skipping to next user'.format(err))
                    continue
                else:
                    self.logger.error(
                        'Sorry, an error occured: {}'.format(err))
                    self.aborting = True
                    return self
        self.logger.info(
            "--> List followers : {} ".format(len(followers_list)))

        return followers_list

    def interact_user_following(self, usernames, amount=10, randomize=False):

        userToInteract = []
        if not isinstance(usernames, list):
            usernames = [usernames]
        try:
            for user in usernames:
                userToInteract += get_given_user_following(
                    self.browser,
                    user,
                    amount,
                    self.dont_include,
                    self.username,
                    randomize,
                    self.logger)
        except (TypeError, RuntimeWarning) as err:
            if isinstance(err, RuntimeWarning):
                self.logger.warning(
                    u'Warning: {} , stopping follow_users'.format(err))
                return self
            else:
                self.logger.error('Sorry, an error occured: {}'.format(err))
                self.aborting = True
                return self

        self.logger.info('--> Users: {}'.format(len(userToInteract)))

        userToInteract = random.sample(userToInteract, int(ceil(
            self.user_interact_percentage * len(userToInteract) / 100)))

        self.like_by_users(userToInteract,
                           self.user_interact_amount,
                           self.user_interact_random,
                           self.user_interact_media)

        return self

    def follow_user_followers(self,
                              usernames,
                              amount=10,
                              randomize=False,
                              interact=False,
                              sleep_delay=600):

        userFollowed = []
        if not isinstance(usernames, list):
            usernames = [usernames]
        for user in usernames:

            try:
                userFollowed += follow_given_user_followers(self.browser,
                                                            user,
                                                            amount,
                                                            self.dont_include,
                                                            self.username,
                                                            self.follow_restrict,
                                                            randomize,
                                                            sleep_delay,
                                                            self.blacklist,
                                                            self.logger,
                                                            self.logfolder,
                                                            self.follow_times)

            except (TypeError, RuntimeWarning) as err:
                if isinstance(err, RuntimeWarning):
                    self.logger.warning(
                        u'Warning: {} , skipping to next user'.format(err))
                    continue
                else:
                    self.logger.error(
                        'Sorry, an error occured: {}'.format(err))
                    self.aborting = True
                    return self
        self.logger.info(
            "--> Total people followed : {} ".format(len(userFollowed)))

        if interact:
            self.logger.info('--> User followed: {}'.format(userFollowed))
            userFollowed = random.sample(userFollowed, int(ceil(
                self.user_interact_percentage * len(userFollowed) / 100)))
            self.like_by_users(userFollowed,
                               self.user_interact_amount,
                               self.user_interact_random,
                               self.user_interact_media)

        return self

    def follow_user_following(self,
                              usernames,
                              amount=10,
                              randomize=False,
                              interact=False,
                              sleep_delay=600):
        userFollowed = []
        if not isinstance(usernames, list):
            usernames = [usernames]

        for user in usernames:
            try:
                userFollowed += follow_given_user_following(self.browser,
                                                            user,
                                                            amount,
                                                            self.dont_include,
                                                            self.username,
                                                            self.follow_restrict,
                                                            randomize,
                                                            sleep_delay,
                                                            self.blacklist,
                                                            self.logger,
                                                            self.logfolder,
                                                            self.follow_times)

            except (TypeError, RuntimeWarning) as err:
                if isinstance(err, RuntimeWarning):
                    self.logger.warning(
                        u'Warning: {} , skipping to next user'.format(err))
                    continue
                else:
                    self.logger.error(
                        'Sorry, an error occured: {}'.format(err))
                    self.aborting = True

                    return self
        self.logger.info("--> Total people followed : {} "
                         .format(len(userFollowed)))

        if interact:
            self.logger.info('--> User followed: {}'.format(userFollowed))
            userFollowed = random.sample(userFollowed, int(ceil(
                self.user_interact_percentage * len(userFollowed) / 100)))
            self.like_by_users(userFollowed,
                               self.user_interact_amount,
                               self.user_interact_random,
                               self.user_interact_media)

        return self

    def unfollow_users(self,
                       amount=10,
                       onlyInstapyFollowed=False,
                       onlyInstapyMethod='FIFO',
                       sleep_delay=600,
                       onlyNotFollowMe=False,
                       unfollow_after=None):
        """Unfollows (default) 10 users from your following list"""

        if unfollow_after is not None:
            if not python_version().startswith(('2.7', '3')):
                self.logger.info("`unfollow_after` argument is not available for Python versions below 2.7")
                unfollow_after = None

        if onlyInstapyFollowed:
            self.automatedFollowedPool = set_automated_followed_pool(self.username,
                                                                     self.logger,
                                                                     self.logfolder,
                                                                     unfollow_after)

        try:
            unfollowNumber = unfollow(self.browser,
                                      self.username,
                                      amount,
                                      self.dont_include,
                                      onlyInstapyFollowed,
                                      onlyInstapyMethod,
                                      self.automatedFollowedPool,
                                      sleep_delay,
                                      onlyNotFollowMe,
                                      self.logger,
                                      self.logfolder)
            self.logger.info(
                "--> Total people unfollowed : {} ".format(unfollowNumber))
            self.unfollowNumber += unfollowNumber

        except (TypeError, RuntimeWarning) as err:
            if isinstance(err, RuntimeWarning):
                self.logger.warning(
                    u'Warning: {} , stopping unfollow_users'.format(err))
                return self
            else:
                self.logger.info('Sorry, an error occured: {}'.format(err))
                self.aborting = True
                return self

        return self

    def like_by_feed(self, **kwargs):
        """Like the users feed"""
        for i in self.like_by_feed_generator(**kwargs):
            pass
        return self

    def like_by_feed_generator(self,
                     amount=50,
                     randomize=False,
                     unfollow=False,
                     interact=False):
        """Like the users feed"""

        if self.aborting:
            return

        liked_img = 0
        already_liked = 0
        inap_img = 0
        commented = 0
        followed = 0
        skipped_img = 0
        num_of_search = 0
        history = []

        while liked_img < amount:
            try:
                # Gets another load of links to be tested
                links = get_links_from_feed(self.browser,
                                            amount,
                                            num_of_search,
                                            self.logger)
            except NoSuchElementException:
                self.logger.warning('Too few images, aborting')
                self.aborting = True
                return

            num_of_search += 1

            for i, link in enumerate(links):
                if liked_img == amount:
                    break
                if randomize and random.choice([True, False]):
                    self.logger.warning('Post Randomly Skipped...\n')
                    skipped_img += 1
                else:
                    if link in history:
                        self.logger.info('This link has already '
                                         'been visited: {}'
                                         .format(link))
                    else:
                        self.logger.info('New link found...')
                        history.append(link)
                        self.logger.info('[{} posts liked /{} amount]'
                                         .format(liked_img, amount))
                        self.logger.info(link)

                        try:
                            inappropriate, user_name, is_video, reason = (
                                check_link(self.browser,
                                           link,
                                           self.dont_like,
                                           self.ignore_if_contains,
                                           self.ignore_users,
                                           self.username,
                                           self.like_by_followers_upper_limit,
                                           self.like_by_followers_lower_limit,
                                           self.logger)
                            )

                            if not inappropriate:
                                liked = like_image(self.browser,
                                                   user_name,
                                                   self.blacklist,
                                                   self.logger,
                                                   self.logfolder)

                                if liked:
                                    username = (self.browser.
                                                find_element_by_xpath(
                                                    '//article/header/div[2]/'
                                                    'div[1]/div/a'))

                                    username = username.get_attribute("title")
                                    name = []
                                    name.append(username)

                                    if interact:
                                        self.logger.info(
                                            '--> User followed: {}'
                                            .format(name))
                                        self.like_by_users(
                                            name,
                                            self.user_interact_amount,
                                            self.user_interact_random,
                                            self.user_interact_media)

                                    liked_img += 1
                                    checked_img = True
                                    temp_comments = []
                                    commenting = random.randint(
                                        0, 100) <= self.comment_percentage
                                    following = random.randint(
                                        0, 100) <= self.follow_percentage

                                    if (self.use_clarifai and
                                            (following or commenting)):
                                        try:
                                            checked_img, temp_comments = (
                                                check_image(
                                                    self.browser,
                                                    self.clarifai_api_key,
                                                    self.clarifai_img_tags,
                                                    self.logger,
                                                    self.clarifai_full_match)
                                            )
                                        except Exception as err:
                                            self.logger.error(
                                                'Image check error:'
                                                ' {}'.format(err))

                                    if (self.do_comment and
                                        user_name not in self.dont_include and
                                            checked_img and commenting):
                                        if temp_comments:
                                            # use clarifai related
                                            # comments only!
                                            comments = temp_comments
                                        elif is_video:
                                            comments = (
                                                self.comments +
                                                self.video_comments)
                                        else:
                                            comments = (
                                                self.comments +
                                                self.photo_comments)
                                        commented += comment_image(
                                                        self.browser,
                                                        user_name,
                                                        comments,
                                                        self.blacklist,
                                                        self.logger,
                                                        self.logfolder)
                                    else:
                                        self.logger.info('--> Not commented')
                                        sleep(1)

                                    if (self.do_follow and
                                        user_name not in self.dont_include and
                                        checked_img and
                                        following and
                                        self.follow_restrict.get(
                                            user_name, 0) < self.follow_times):
                                        followed += follow_user(
                                            self.browser,
                                            self.follow_restrict,
                                            self.username,
                                            user_name,
                                            self.blacklist,
                                            self.logger,
                                            self.logfolder)
                                    else:
                                        self.logger.info('--> Not following')
                                        sleep(1)

                                    yield self
                                else:
                                    already_liked += 1
                            else:
                                self.logger.info(
                                    '--> Image not liked: {}'.format(reason.encode('utf-8')))
                                inap_img += 1
                                if reason == 'Inappropriate' and unfollow:
                                    unfollow_user(self.browser, self.logger)
                        except NoSuchElementException as err:
                            self.logger.error('Invalid Page: {}'.format(err))

        self.logger.info('Liked: {}'.format(liked_img))
        self.logger.info('Already Liked: {}'.format(already_liked))
        self.logger.info('Inappropriate: {}'.format(inap_img))
        self.logger.info('Commented: {}'.format(commented))
        self.logger.info('Followed: {}'.format(followed))
        self.logger.info('Randomly Skipped: {}'.format(skipped_img))

        self.followed += followed
        self.liked_img += liked_img
        self.already_liked += already_liked
        self.inap_img += inap_img
        self.commented += commented

        return

    def set_dont_unfollow_active_users(self, enabled=False, posts=4):
        """Prevents unfollow followers who have liked one of
        your latest X posts"""

        # do nothing
        if not enabled:
            return

        # list of users who liked our media
        active_users = get_active_users(self.browser,
                                        self.username,
                                        posts,
                                        self.logger)

        for user in active_users:
            # include active user to not unfollow list
            self.dont_include.append(user)

    def set_blacklist(self, enabled, campaign):
        """Enable/disable blacklist. If enabled, adds users to a blacklist after
        interact with and adds users to dont_include list"""

        if enabled is False:
            return

        self.blacklist['enabled'] = True
        self.blacklist['campaign'] = campaign

        try:
            with open('{}blacklist.csv'.format(self.logfolder), 'r') as blacklist:
                reader = csv.DictReader(blacklist)
                for row in reader:
                    if row['campaign'] == campaign:
                        self.dont_include.append(row['username'])
        except:
            self.logger.info('Campaign {} first run'.format(campaign))

    def end(self):
        """Closes the current session"""
        dump_follow_restriction(self.follow_restrict, self.logfolder)
        try:
            self.browser.delete_all_cookies()
            self.browser.quit()
        except WebDriverException as exc:
            self.logger.warning('Could not locate Chrome: {}'.format(exc))

        if self.nogui:
            self.display.stop()

        self.logger.info('Session ended - {}'.format(
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        self.logger.info('-' * 20 + '\n\n')

        with open('{}followed.txt'.format(self.logfolder), 'w') as followFile:
            followFile.write(str(self.followed))

    def follow_by_tags(self,
                     tags=None,
                     amount=50,
                     media=None,
                     skip_top_posts=True,
                     use_smart_hashtags=False):
        if self.aborting:
            return self

        inap_img = 0
        followed = 0

        # if smart hashtag is enabled
        if use_smart_hashtags is True and self.smart_hashtags is not []:
            print('Using smart hashtags')
            tags = self.smart_hashtags

        # deletes white spaces in tags
        tags = [tag.strip() for tag in tags]

        tags = tags or []

        for index, tag in enumerate(tags):
            self.logger.info('Tag [{}/{}]'.format(index + 1, len(tags)))
            self.logger.info('--> {}'.format(tag.encode('utf-8')))

            try:
                links = get_links_for_tag(self.browser,
                                          tag,
                                          amount,
                                          self.logger,
                                          media,
                                          skip_top_posts)
            except NoSuchElementException:
                self.logger.error('Too few images, skipping this tag')
                continue

            for i, link in enumerate(links):
                self.logger.info('[{}/{}]'.format(i + 1, len(links)))
                self.logger.info(link)

                try:
                    inappropriate, user_name, is_video, reason = (
                        check_link(self.browser,
                                   link,
                                   self.dont_like,
                                   self.ignore_if_contains,
                                   self.ignore_users,
                                   self.username,
                                   self.like_by_followers_upper_limit,
                                   self.like_by_followers_lower_limit,
                                   self.logger)
                    )

                    if not inappropriate:
                        followed += follow_user(self.browser,
                                                        self.follow_restrict,
                                                        self.username,
                                                        user_name,
                                                        self.blacklist,
                                                        self.logger,
                                                        self.logfolder)
                    else:
                        self.logger.info(
                            '--> User not followed: {}'.format(reason))
                        inap_img += 1
                except NoSuchElementException as err:
                    self.logger.error('Invalid Page: {}'.format(err))

        self.logger.info('Inappropriate: {}'.format(inap_img))
        self.logger.info('Followed: {}'.format(followed))

        self.followed += followed
        self.inap_img += inap_img

        return self
