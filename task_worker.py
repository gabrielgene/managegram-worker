#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import pika
from instapy import InstaPy
import json

def insta_bot(body):
    try:
        data = json.loads((body).decode("utf-8"))
        insta_username = data['user']
        insta_password = data['pass']
        session = InstaPy(username=insta_username,
                    password=insta_password,
                    headless_browser=True,
                    multi_logs=True)

        if (data['status'] != 'stop'):
            session.login()

            session.set_upper_follower_count(limit=999999)

            # actions
            if (data['tag_type'] == 'enable'):
                session.follow_by_tags(data['tag_list'], amount=1)
            elif (data['profile_type'] == 'enable'):
                session.follow_user_followers(data['profile_list'], amount=1, randomize=True, sleep_delay=60)

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
