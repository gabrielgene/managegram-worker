
#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
import pika
from instapy import InstaPy
import json

def send_to_queue(followers):
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    channel.queue_declare(queue='dmlist_queue', durable=True)

    message = ','.join(followers)

    channel.basic_publish(exchange='',
                      routing_key='dmlist_queue',
                      body=message,
                      properties=pika.BasicProperties(
                         delivery_mode = 2, # make message persistent
                      ))
    print(" [x] Sent %r" % message)
    connection.close()

def insta_bot(body):
    try:
        data = json.loads((body).decode("utf-8"))
        insta_username = data['user']#'managerinsta97'
        insta_password = data['pass']#insta@123'
        session = InstaPy(username=insta_username,
                    password=insta_password,
                    headless_browser=True,
                    multi_logs=True)

        if (data['status'] != 'stop'):
            session.login()

            # actions
            if (data['dm_type'] == 'enable'):
                followers_list = session.list_followers([insta_username])
                send_to_queue(followers_list)


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
                      queue='dm_queue')

channel.start_consuming()
