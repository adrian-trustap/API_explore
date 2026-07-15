"""
api_tree.py

Builds a tree.json file for the D3 API tree viewer.

Two modes:

1. Plain mode (one spec):
     python api_tree.py v2-spec.yaml
   Produces a plain endpoint tree - no highlighting, no diff data.

2. Diff mode (two specs):
     python api_tree.py v1-spec.yaml --compare v2-spec.yaml
   Produces the same tree, but every endpoint (and every method on that
   endpoint) is tagged with a status:
     - "added"     endpoint/method exists only in the second (v2) spec
     - "removed"   endpoint/method exists only in the first (v1) spec
     - "unchanged" endpoint/method exists in both, methods identical
     - "modified"  endpoint exists in both, but its set of methods differs

The output JSON is consumed by the accompanying HTML viewer.
"""
import argparse
import json
import sys

import yaml

HTTP_METHODS = {'get', 'post', 'put', 'delete', 'patch', 'options', 'head'}


class TreeNode:
    def __init__(self, name):
        self.name = name
        self.methods_v1 = set()
        self.methods_v2 = set()
        self.children = {}

    def add_path(self, path_parts, method, version):
        if not path_parts:
            if version == 1:
                self.methods_v1.add(method.upper())
            else:
                self.methods_v2.add(method.upper())
            return
        head, *tail = path_parts
        child = self.children.setdefault(head, TreeNode(head))
        child.add_path(tail, method, version)


def load_spec(path):
    with open(path, 'r') as f:
        if path.endswith(('.yaml', '.yml')):
            return yaml.safe_load(f)
        return json.load(f)


def build_tree(spec, version, root=None):
    """Walk a spec's paths into `root`, tagging methods with `version` (1 or 2)."""
    if root is None:
        root = TreeNode('')
    for path, methods in spec.get('paths', {}).items():
        if not isinstance(methods, dict):
            continue
        parts = [p for p in path.strip('/').split('/') if p]
        for method in methods.keys():
            if method.lower() in HTTP_METHODS:
                root.add_path(parts, method, version)
    return root


def endpoint_status(methods_v1, methods_v2):
    if not methods_v1 and methods_v2:
        return "added"
    if methods_v1 and not methods_v2:
        return "removed"
    if methods_v1 == methods_v2:
        return "unchanged"
    return "modified"


def method_list(methods_v1, methods_v2, diff_mode):
    all_methods = sorted(methods_v1 | methods_v2)
    out = []
    for m in all_methods:
        if not diff_mode:
            status = "unchanged"
        elif m in methods_v1 and m in methods_v2:
            status = "unchanged"
        elif m in methods_v2:
            status = "added"
        else:
            status = "removed"
        out.append({"method": m, "status": status})
    return out


def to_d3_json(node, diff_mode):
    children = [to_d3_json(c, diff_mode) for c in sorted(node.children.values(), key=lambda n: n.name)]
    label = f"/{node.name}" if node.name else "/"
    result = {"name": label}

    has_methods = bool(node.methods_v1 or node.methods_v2)
    if has_methods:
        result["methods"] = method_list(node.methods_v1, node.methods_v2, diff_mode)
        if diff_mode:
            result["status"] = endpoint_status(node.methods_v1, node.methods_v2)

    if children:
        result["children"] = children
    return result


def main():
    parser = argparse.ArgumentParser(description="Build tree.json for the API tree viewer.")
    parser.add_argument('spec', help='Path to the API spec (the v1/base spec if using --compare).')
    parser.add_argument('--compare', '-c', metavar='SPEC_V2',
                         help='Path to a second spec to diff against `spec`. Enables diff mode.')
    parser.add_argument('--output', '-o', default='tree.json', help='Output JSON path (default: tree.json).')
    args = parser.parse_args()

    root = TreeNode('')
    build_tree(load_spec(args.spec), 1, root)

    diff_mode = bool(args.compare)
    if diff_mode:
        build_tree(load_spec(args.compare), 2, root)

    tree_json = to_d3_json(root, diff_mode)

    with open(args.output, 'w') as f:
        json.dump(tree_json, f, indent=2)

    if diff_mode:
        print(f"Diff tree ({args.spec} -> {args.compare}) saved to {args.output}")
    else:
        print(f"Endpoint tree saved to {args.output}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python api_tree.py path/to/spec.yaml")
        print("  python api_tree.py path/to/v1-spec.yaml --compare path/to/v2-spec.yaml")
        sys.exit(1)
    main()