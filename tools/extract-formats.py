#! /usr/bin/python3
# Simple script to parse specs and produce CSV files.
# Released by Rusty Russell under CC0:
# https://creativecommons.org/publicdomain/zero/1.0/

from optparse import OptionParser
import sys
import re
import fileinput


def main(options, args=None, output=sys.stdout, lines=None):
    # Example inputs:
    # 1. type: 17 (`error`) (`optionXXX`)
    # 2. data:
    #    * [`8`:`channel_id`]
    #    * [`4`:`len`]
    #    * [`len`:`data`] (optionXXX)
    #    * [`2`:`num_inputs`]
    #    * [`num_inputs*input_info`]
    #
    # output:
    #   error,17
    #   error,0,channel_id,8
    #   error,8,len,4
    #   error,12,data,len
    #   error,12+len,num_inputs,2
    #   error,14+len,input_info,num_inputs*input_info
    #
    # 1. type: PERM|NODE|3 (`required_node_feature_missing`)
    #
    # 1. type: 261 (`query_short_channel_ids`) (`gossip_queries`)
    # 2. data:
    #     * [`32`:`chain_hash`]
    #     * [`2`:`len`]
    #     * [`len`:`encoded_short_ids`]
    #     * [`tlvs`:`query_short_channel_ids_tlvs`]
    #
    # output:
    #   query_short_channel_ids_tlvs,17,gossip_queries
    #   query_short_channel_ids_tlvs,0,chainhash,32
    #   query_short_channel_ids_tlvs,32,len,2
    #   query_short_channel_ids_tlvs,34,encoded_short_ids,len
    #   query_short_channel_ids_tlvs,34+len,query_short_channel_ids_tlv,tlv
    #
    # 1. tlv: `query_short_channel_ids_tlvs`
    # 2. types:
    #    1. type: 1 (`query_flags`)
    #    2. data:
    # 	      * [`1`:`encoding_type`]
    # 	      * [`tlv_len-1`:`encoded_query_flags`]
    #
    # output:
    #  query_flags,1,query_short_channel_ids_tlvs
    #  query_flags,0,encoding_type,1
    #  query_flags,1,encoded_query_flags,tlv_len-1
    #
    # 1. subtype: `input_info`
    # 2. data:
    #    * [`8`:`satoshis`]
    #    * [`32`:`prevtx_txid`]
    #
    # output:
    #  input_info
    #  input_info,0,satoshis,8
    #  input_info,8,prev_txid,32
    #
    message = None
    havedata = None
    tlv = None
    tlv_msg_count = 0
    typeline = re.compile(
        '(?P<leading>\s*)1\. (?P<type>((sub)*?type|tlv)):( (?P<value>[-0-9A-Za-z_|]+))? \(?`(?P<name>[A-Za-z2_]+)`\)?( \(`?(?P<option>[^)`]*)`?\))?')
    dataline = re.compile(
        '\s+\* \[`((?P<size>[-_a-zA-Z0-9*+]+)`:`(?P<name>[_a-z0-9]+)|(?P<count>[_a-z0-9+]+)(?P<multi>\*)(?P<subtype>[_a-z0-9]+))`\]( \(`?(?P<option>[^)`]*)`?\))?')

    if lines is None:
        lines = fileinput.input(args)

    for i, line in enumerate(lines):
        line = line.rstrip()
        linenum = i+1

        match = typeline.fullmatch(line)
        if match:
            if match.group('type') == 'tlv':
                if tlv:
                    raise ValueError('{}:Found a tlv while I was already in a tlv'
                                     .format(linenum))
                tlv = match.group('name')
                tlv_msg_count = 0
                continue

            if message and not tlv:
                raise ValueError('{}:Found a message while I was already in a '
                                 'message'.format(linenum))

            message = match.group('name')
            if tlv is not None and len(match.group('leading')) == 0:
                tlv = None
            if options.output_types:
                if tlv:
                    print("{},{},{}".format(
                        match.group('name'),
                        match.group('value'),
                        tlv), file=output)
                else:
                    if not match.group('value'):
                        print("{}".format(match.group('name')), file=output)
                    else:
                        print("{},{}".format(match.group('name'),
                                             str(match.group('value'))), file=output)
            havedata = None
            if tlv:
                tlv_msg_count += 1
        elif tlv and tlv_msg_count == 0:
            if line != '2. types:':
                tlv = None
        elif message is not None and havedata is None:
            if line.lstrip() != '2. data:':
                message = None
            havedata = True
            dataoff = 0
            off_extraterms = ""
            prev_field = ""
        elif message is not None and havedata is not None:
            match = dataline.fullmatch(line)
            if match:
                if match.group('multi'):
                    size = ''.join([prev_field, '*', match.group('subtype')])
                    print("{},{}{},{},{}".format(
                        message,
                        dataoff,
                        off_extraterms,
                        match.group('subtype'),
                        size))
                    off_extraterms += '+' + size
                    prev_field = match.group('subtype')
                else:
                    if options.output_fields:
                        print("{},{}{},{},{}".format(
                            message,
                            dataoff,
                            off_extraterms,
                            match.group('name'),
                            match.group('size')), file=output, end='')
                        if match.group('option'):
                            print(",{}".format(match.group('option')), file=output)
                        else:
                            print('', file=output)

                    prev_field = match.group('name')
                    # Size can be variable.
                    try:
                        dataoff += int(match.group('size'))
                    except ValueError:
                        # Offset has variable component.
                        off_extraterms = off_extraterms + "+" + match.group('size')
            else:
                message = None


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option(
        "--message-types",
        action="store_true",
        dest="output_types",
        default=False,
        help="Output MESSAGENAME,VALUE for every message"
    )
    parser.add_option(
        "--message-fields",
        action="store_true",
        dest="output_fields",
        default=False,
        help="Output MESSAGENAME,OFFSET,FIELDNAME,SIZE for every message"
    )

    (options, args) = parser.parse_args()

    main(options, args)
