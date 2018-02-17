#!/usr/bin/env python
import pika
from instapy import InstaPy
import json

def insta_bot(body):
    # set headless_browser=True if you want to run InstaPy on a server
    try:
        data = json.loads((body).decode("utf-8"))
        insta_username = data['user']#'managerinsta97'
        insta_password = data['pass']#insta@123'
        # set these if you're locating the library in the /usr/lib/pythonX.X/ directory
        # Settings.database_location = '/path/to/instapy.db'
        # Settings.browser_location = '/path/to/chromedriver'

        session = InstaPy(username=insta_username,
                        password=insta_password,
                        headless_browser=True,
                        multi_logs=True)
        session.login()

        # actions
        if (data['tag']):
            session.follow_by_tags(data['tags_list'], amount=7)
        elif (data['follow']):
            session.follow_user_followers(data['profiles'], amount=7, randomize=True, sleep_delay=60)

    finally:
        # end the bot session
        session.end()

connection = pika.BlockingConnection(pika.ConnectionParameters(host='127.0.0.1'))
channel = connection.channel()

channel.queue_declare(queue='task_queue', durable=True)
print(' [*] Waiting for messages. To exit press CTRL+C')

def callback(ch, method, properties, body):
    print(" [x] Received %r" % body)
    insta_bot(body)
    print(" [x] Done")
    ch.basic_ack(delivery_tag = method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(callback,
                      queue='task_queue')

channel.start_consuming()
