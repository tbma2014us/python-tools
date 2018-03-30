#!/usr/bin/env python
import logging
import os
import sys

import argparse
import aws_encryption_sdk
import boto3
import botocore.exceptions


class ArgsParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            'description',
            'Decrypts files encrypted with kms-encrypt')
        argparse.ArgumentParser.__init__(self, *args, **kwargs)
        self.formatter_class = argparse.ArgumentDefaultsHelpFormatter
        self.epilog = 'You need to create KMS keys before using this. By default it tries to use "alias/ec2" key'
        self.options = None
        self.add_argument('-a', '--alias', dest='key_alias', help='KMS key alias', default='alias/ec2')
        self.add_argument('-p', '--profile', dest='profile', help='AWS profile to use')
        self.add_argument('-r', '--region', dest='region', default='us-west-2', help='AWS region to connect')
        self.add_argument('-v', '--verbose', dest='verbose', action='store_true', default=False, help='Be verbose')
        self.add_argument('in_file', help='Name of the encrypted input file',)
        self.add_argument('out_file', help='Name of the output file', nargs='?')

    def error(self, message):
        sys.stderr.write('Error: %s\n' % message)
        self.print_help()
        sys.exit(2)

    def parse_args(self, *args, **kwargs):
        options = argparse.ArgumentParser.parse_args(self, *args, **kwargs)
        options.log_format = '%(filename)s:%(lineno)s[%(process)d]: %(levelname)s %(message)s'
        options.name = os.path.basename(__file__)
        if not options.out_file and options.in_file.endswith('.enc'):
            options.out_file = options.in_file[:-4]
        elif not options.out_file:
            self.error('Please specify output file')
        self.options = options
        return options


class KmsDecrypt(object):
    def __init__(self, _session):
        self.session = _session

    def alias_exists(self, _alias):
        aliases = self.session.client('kms').list_aliases()
        return any([k for k in aliases['Aliases'] if k['AliasName'] == _alias])

    def build_kms_master_key_provider(self, alias):
        if not self.alias_exists(alias):
            raise SystemExit('FATAL: alias %s does not exists in %s' % (
                alias,
                self.session.region_name,
            ))
        arn_template = 'arn:aws:kms:{region}:{account_id}:{alias}'
        kms_master_key_provider = aws_encryption_sdk.KMSMasterKeyProvider()
        account_id = self.session.client('sts').get_caller_identity()['Account']
        kms_master_key_provider.add_master_key(arn_template.format(
            region=self.session.region_name,
            account_id=account_id,
            alias=alias
        ))
        return kms_master_key_provider

    def decrypt_file(self, key_alias, input_filename, output_filename):
        key_provider = self.build_kms_master_key_provider(key_alias)
        with open(input_filename, 'rb') as infile, \
                open(output_filename, 'wb') as outfile, \
                aws_encryption_sdk.stream(
                    mode='d',
                    source=infile,
                    key_provider=key_provider
                ) as decryptor:
            for chunk in decryptor:
                outfile.write(chunk)


def main(args=sys.argv[1:]):
    my_parser = ArgsParser()
    options = my_parser.parse_args(args)

    for m in ['botocore', 'boto3', 'aws_encryption_sdk']:
        not options.verbose and logging.getLogger(m).setLevel(logging.CRITICAL)

    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=options.log_format)
    session = boto3.session.Session()

    k = KmsDecrypt(session)
    try:
        k.decrypt_file(
            options.key_alias,
            options.in_file,
            options.out_file
        )
    except botocore.exceptions.ClientError as e:
        raise SystemExit(e)


if __name__ == '__main__':
    main()
