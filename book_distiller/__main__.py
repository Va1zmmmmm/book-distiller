import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .cards import card_input, instruction, build_card
from .books import book_input, chunks_for, MAP_INSTRUCTION, build_book, load_book, build_session
from .evidence import InvalidInput, required_string, string_list, sha
from .io import load_json, write_bundle, json_bytes, checked_read
from .provider import Provider

def main(argv=None):
    parser = argparse.ArgumentParser(description='读后卡片与按阅读位置导出的陪读材料；默认不联网')
    subs = parser.add_subparsers(dest='command', required=True)
    for command in ('card', 'prepare'):
        p = subs.add_parser(command)
        p.add_argument('input'); p.add_argument('--out', required=True)
        mode = p.add_mutually_exclusive_group()
        mode.add_argument('--response'); mode.add_argument('--online', action='store_true')
        p.add_argument('--config'); p.add_argument('--cache-dir')
    p = subs.add_parser('session'); p.add_argument('bundle'); p.add_argument('--chapter', required=True)
    p.add_argument('--through-line', type=int); p.add_argument('--out', required=True)
    p = subs.add_parser('note'); p.add_argument('bundle'); p.add_argument('--event', required=True)
    p = subs.add_parser('review'); p.add_argument('bundle')
    p.add_argument('--decision', choices=['accept', 'partial', 'reject'], required=True)
    p.add_argument('--accept-claim', type=int, action='append', default=[])
    p.add_argument('--accept-takeable', action='store_true'); p.add_argument('--note', default='')
    args = parser.parse_args(argv)
    try:
        if getattr(args, 'out', None) and Path(args.out).exists():
            raise InvalidInput('输出目录已存在，请选择新目录；不会覆盖手工文件')
        if args.command in ('card', 'prepare'):
            if (args.config or args.cache_dir) and not args.online:
                raise InvalidInput('--config/--cache-dir只配合显式--online使用')
            data, input_hash = load_json(args.input)
            if args.command == 'card':
                card_input(data)
            else:
                book_input(data)
            if args.online and not args.config:
                raise InvalidInput('--online需要--config')
            provider = Provider(args.config, args.cache_dir) if args.online else None
            origin = 'llm' if provider else 'response-import' if args.response else 'source-only'
            if args.command == 'card':
                if not provider and not args.response:
                    raise InvalidInput('卡片需要--response或显式--online；本地程序不伪造AI解读')
                result = provider.complete(instruction(), data) if provider else load_json(args.response)[0]
                files = build_card(data, result, input_hash, origin)
            else:
                responses = None
                if provider:
                    responses = {c['id']: provider.complete(MAP_INSTRUCTION, c) for c in chunks_for(data)}
                elif args.response:
                    responses = load_json(args.response)[0].get('chunks')
                    if not isinstance(responses, dict):
                        raise InvalidInput('章节响应需要chunks对象')
                files = build_book(data, responses, input_hash, origin)
            write_bundle(args.out, files)
            print('完成：结果写入指定新目录；候选仍需读者查看')
        elif args.command == 'session':
            write_bundle(args.out, build_session(args.bundle, args.chapter, args.through_line))
            print('完成：只导出指定已读范围')
        elif args.command == 'note':
            manifest, _ = load_book(args.bundle)
            event, _ = load_json(args.event)
            if set(event) - {'chapter_id', 'reader', 'ai', 'questions', 'corrections'}:
                raise InvalidInput('note含未知字段')
            if event.get('chapter_id') not in {c['id'] for c in manifest['chapters']}:
                raise InvalidInput('笔记章节不存在')
            for name in ('reader', 'ai'):
                if name in event and not isinstance(event[name], str):
                    raise InvalidInput(f'{name}必须是字符串')
            for name in ('questions', 'corrections'):
                string_list(event.get(name, []), name)
            if not any(event.get(k) for k in ('reader', 'ai', 'questions', 'corrections')):
                raise InvalidInput('笔记为空')
            event['recorded_at'] = datetime.now(timezone.utc).isoformat()
            event['origin'] = 'caller-provided; reader/ai归属由填写者负责，未自动认可AI观点'
            directory = Path(args.bundle) / 'notes'; directory.mkdir(exist_ok=True)
            with (directory / (uuid.uuid4().hex + '.json')).open('xb') as stream:
                stream.write(json_bytes(event))
            print('完成：新增笔记事件，既有记录保留')
        elif args.command == 'review':
            root = Path(args.bundle)
            card, _ = load_json(root / 'card.json')
            references, _ = load_json(root / 'references.json')
            checked_read(root, 'card.json', references['card_sha256'])
            checked_read(root, 'input.json', references['input_copy_sha256'])
            claims = args.accept_claim
            if any(n < 1 or n > len(card['core_claims']) for n in claims):
                raise InvalidInput('接受的观点编号超出范围')
            if args.decision == 'partial' and not (claims or args.accept_takeable):
                raise InvalidInput('partial需明确接受哪些观点或可带走内容')
            if args.decision != 'partial' and (claims or args.accept_takeable):
                raise InvalidInput('指定接受项仅用于partial')
            if args.accept_takeable and card.get('takeable') is None:
                raise InvalidInput('卡片没有可带走内容')
            accepted = list(range(1, len(card['core_claims']) + 1)) if args.decision == 'accept' else sorted(set(claims))
            takeable = card.get('takeable') is not None if args.decision == 'accept' else args.accept_takeable
            event = {'decision': args.decision, 'accepted_claims': accepted,
                     'accept_takeable': takeable, 'note': args.note,
                     'candidate_sha256': references['card_sha256'],
                     'recorded_at': datetime.now(timezone.utc).isoformat()}
            directory = root / 'reviews'; directory.mkdir(exist_ok=True)
            with (directory / (uuid.uuid4().hex + '.json')).open('xb') as stream:
                stream.write(json_bytes(event))
            print('完成：记录人工判断，卡片候选保留原样')
        return 0
    except (InvalidInput, OSError, KeyError, TypeError, ValueError) as exc:
        # Do not print arbitrary model/source text, URLs, keys, or provider payloads.
        message = str(exc) if isinstance(exc, InvalidInput) else '文件/数据结构错误，请检查输入格式与读写权限'
        print('失败：' + message, file=sys.stderr)
        return 2

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
    sys.exit(main())
