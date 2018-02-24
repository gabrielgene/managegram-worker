#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import pika
from instapy import InstaPy
import json

def send_to_queue(data):
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    channel.queue_declare(queue='dmlist_queue', durable=True)

    channel.basic_publish(exchange='',
                      routing_key='dmlist_queue',
                      body=data,
                      properties=pika.BasicProperties(
                         delivery_mode = 2, # make message persistent
                      ))
    print(" [x] Sent %r" % data)
    connection.close()

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

            # actions
            if (data['dm_type'] == 'enable'):
                followers_list = session.list_followers([insta_username])
                data['followers_list'] = followers_list
                send_to_queue(json.dumps(data))


    finally:
        # end the bot session
        session.end()

connection = pika.BlockingConnection(pika.ConnectionParameters(host='127.0.0.1'))
channel = connection.channel()

channel.queue_declare(queue='dm_queue', durable=True)
print(' [*] Waiting for dm messages. To exit press CTRL+C')

def callback(ch, method, properties, body):
    print(" [x] Received %r" % body)
    insta_bot(body)
    print(" [x] Done")
    ch.basic_ack(delivery_tag = method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(callback,
                      queue='dm_queue')

channel.start_consuming()
