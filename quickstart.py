#!/usr/bin/env python
import pika
from instapy import InstaPy

def insta(tag):
    # set headless_browser=True if you want to run InstaPy on a server
    try:
        insta_username = 'managerinsta97'
        insta_password = 'insta@123'
        # set these if you're locating the library in the /usr/lib/pythonX.X/ directory
        # Settings.database_location = '/path/to/instapy.db'
        # Settings.browser_location = '/path/to/chromedriver'

        session = InstaPy(username=insta_username,
                        password=insta_password,
                        headless_browser=True,
                        multi_logs=True)
        session.login()

        # settings
        session.set_upper_follower_count(limit=2500)
        session.set_do_comment(True, percentage=10)
        session.set_comments(['aMEIzing!', 'So much fun!!', 'Nicey!'])
        session.set_dont_include(['friend1', 'friend2', 'friend3'])
        session.set_dont_like(['pizza', 'girl'])

        # actions
        session.follow_by_tags([tag], amount=1)

    finally:
        # end the bot session
        session.end()

connection = pika.BlockingConnection(pika.ConnectionParameters(host='127.0.0.1'))
channel = connection.channel()

channel.queue_declare(queue='task_queue', durable=True)
print(' [*] Waiting for messages. To exit press CTRL+C')

def callback(ch, method, properties, body):
    print(" [x] Received %r" % body)
    insta(body)
    print(" [x] Done")
    ch.basic_ack(delivery_tag = method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(callback,
                      queue='task_queue')

channel.start_consuming()
