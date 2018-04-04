#!/usr/bin/env python
import logging
import sys

import argparse
import boto3
import botocore.exceptions

LOG_FORMAT = '%(filename)s:%(lineno)s[%(process)d]: %(levelname)s %(message)s'


class ArgsParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            'description',
            'Adds tags to ec2 instances by name or id')
        argparse.ArgumentParser.__init__(self, *args, **kwargs)
        self.options = None
        self.add_argument('-r', '--regions', dest='region', default='us-west-2', help='Region to connect')
        self.add_argument('-p', '--profile', dest='profile', help='Profile to use')
        self.add_argument('--dry-run', dest='dry_run', action='store_true', default=False,
                          help="Don't actually do anything; just print out what would be done")
        self.add_argument('name', help='Name of the EC2 or RDS instance', nargs='+')
        self.add_argument('-t', '--tag', dest='tag', help="name=value for the tag")

    def error(self, message):
        sys.stderr.write('ERROR: %s\n\n' % message)
        self.print_help()
        sys.exit(2)

    def parse_args(self, *args, **kwargs):
        options = argparse.ArgumentParser.parse_args(self, *args, **kwargs)
        if '=' not in options.tag:
            raise SystemExit('Please specify tag as TagName=Value')
        self.options = options
        return options


def lookup(conn, host):
    if host.startswith("i-") and (len(host) == 10 or len(host) == 19):
        instances = conn.instances.filter(InstanceIds=[host])
    else:
        instances = conn.instances.filter(
            Filters=[dict(Name='tag:Name', Values=[host])]
        )
    try:
        return next(iter(instances))
    except StopIteration:
        logging.error('Cannot find %s' % host)
        return


def main(args=sys.argv[1:]):
    myparser = ArgsParser()
    options = myparser.parse_args(args)
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=LOG_FORMAT)

    try:
        session = boto3.session.Session(region_name=options.region, profile_name=options.profile)
        ec2 = session.resource('ec2')
        instances = []

        for hostname in options.name:
            r = lookup(ec2, hostname)
            instances.append(r.id)

        (tag, _, value) = options.tag.partition("=")
        logging.info('Setting tags on %s' % ' '.join(instances))

        ec2.create_tags(
            Resources=instances,
            Tags=[{'Key': tag, 'Value': value}],
            DryRun=options.dry_run,
        )

    except botocore.exceptions.ClientError as e:
        raise SystemExit(e)


if __name__ == '__main__':
    main()
