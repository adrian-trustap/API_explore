import json
from collections import defaultdict
import sys
import yaml  # add this
from collections import Counter, defaultdict

def find_duplicate_endpoint_names(spec):
    """
    Find duplicates based only on the final path segment (endpoint name).
    """
    counter = defaultdict(list)  # name -> list of (path, method)

    for path, methods in spec.get('paths', {}).items():
        endpoint_name = path.strip('/').split('/')[-1]
        for method in methods.keys():
            counter[endpoint_name].append((path, method.upper()))

    duplicates = {name: entries for name, entries in counter.items() if len(entries) > 1}
    return duplicates


def snake_case_tag_path_prefix_stats(spec, max_depth=3):
    tag_prefix_counts = defaultdict(lambda: defaultdict(Counter))

    for path, methods in spec.get('paths', {}).items():
        for method, details in methods.items():
            if not isinstance(details, dict):
                continue
            tags = details.get('tags', [])
            if not tags:
                continue

            # Clean path and split on underscores
            path_parts = path.strip('/').split('/')
            last_segment = path_parts[-1] if path_parts else ''
            snake_parts = [p for p in last_segment.split('_') if p]

            for tag in tags:
                for i in range(1, max_depth + 1):
                    if len(snake_parts) >= i:
                        prefix = '_'.join(snake_parts[:i])
                        tag_prefix_counts[tag][i][prefix] += 1

    return tag_prefix_counts

class TreeNode:
    def __init__(self, name):
        self.name = name
        self.methods = set()
        self.children = {}

    def add_path(self, path_parts, method):
        if not path_parts:
            self.methods.add(method.upper())
            return
        head, *tail = path_parts
        if head not in self.children:
            self.children[head] = TreeNode(head)
        self.children[head].add_path(tail, method)

    def display(self, indent=0):
        indent_str = '  ' * indent
        methods = f" [{', '.join(sorted(self.methods))}]" if self.methods else ""
        print(f"{indent_str}/{self.name}{methods}")
        for child in sorted(self.children.values(), key=lambda x: x.name):
            child.display(indent + 1)

def build_tree(swagger_spec):
    root = TreeNode('')
    paths = swagger_spec.get('paths', {})
    for path, methods in paths.items():
        path_parts = [part for part in path.strip('/').split('/') if part]
        for method in methods.keys():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']:
                root.add_path(path_parts, method)
    return root


def collect_tagged_paths(spec):
    tag_to_paths = defaultdict(list)
    for path, methods in spec.get('paths', {}).items():
        for method, details in methods.items():
            if not isinstance(details, dict):
                continue
            tags = details.get('tags', [])
            for tag in tags:
                tag_to_paths[tag].append((path, method.upper()))
    return tag_to_paths

def build_tree_for_tag(paths_and_methods):
    root = TreeNode('')
    for path, method in paths_and_methods:
        parts = path.strip('/').split('/')
        current = root
        for part in parts:
            current = current.children.setdefault(part, TreeNode(part))  # ← fixed line
        current.methods.add(method)
    return root

def tag_tree_to_d3(tag, tree):
    return {
        "name": tag,
        "children": [to_d3_json(child) for child in tree.children.values()]
    }

def save_tag_grouped_tree(spec, output_path='tree.json'):
    tag_to_paths = collect_tagged_paths(spec)
    tag_groups = spec.get('x-tagGroups', [])
    
    grouped_tree = []

    for group in tag_groups:
        group_name = group.get('name', 'Other')
        tag_entries = group.get('tags', [])
        group_entry = {
            "name": group_name,
            "children": []
        }
        for tag in tag_entries:
            paths = tag_to_paths.get(tag, [])
            tag_tree = build_tree_for_tag(paths)
            group_entry["children"].append(tag_tree_to_d3(tag, tag_tree))
        grouped_tree.append(group_entry)

    with open(output_path, 'w') as f:
        json.dump({"name": "API", "children": grouped_tree}, f, indent=2)

    print(f"Grouped tree saved to {output_path}")




def to_d3_json(node):
    children = [to_d3_json(child) for child in node.children.values()]
    label = f"/{node.name}" if node.name else "/"
    if node.methods:
        label += f" [{', '.join(sorted(node.methods))}]"
    return {
        "name": label,
        "children": children if children else None
    }

def save_as_json(swagger_path, output_path='tree.json'):
    with open(swagger_path, 'r') as f:
        if swagger_path.endswith('.yaml') or swagger_path.endswith('.yml'):
            spec = yaml.safe_load(f)
        else:
            spec = json.load(f)
    tree = build_tree(spec)
    tree_json = to_d3_json(tree)
    save_tag_grouped_tree(spec)
    with open(output_path, 'w') as f:
        json.dump(tree_json, f, indent=2)
    print(f"Tree JSON saved to {output_path}")

def main(swagger_path):
    with open(swagger_path, 'r') as f:
        if swagger_path.endswith('.yaml') or swagger_path.endswith('.yml'):
            spec = yaml.safe_load(f)
        else:
            spec = json.load(f)
    tree = build_tree(spec)
    print("\nAPI Endpoint Tree:")
    tree.display()
    output_path = 'tree.json'
    save_as_json(swagger_path, output_path)
    save_tag_grouped_tree(spec)

    tag_prefix_counts = snake_case_tag_path_prefix_stats(spec, max_depth=3)

    print("\nMost common snake_case path prefixes per tag:")
    for tag, levels in tag_prefix_counts.items():
        print(f"\nTag: {tag}")
        for depth in sorted(levels.keys()):
            print(f"  Depth {depth}:")
            for prefix, count in levels[depth].most_common(5):
                print(f"    {prefix}: {count}")

    # Optional: save to file
    with open('tag_path_prefix_stats.json', 'w') as f:
        # Convert nested defaultdicts to regular dicts
        output = {
            tag: {
                str(depth): dict(prefixes)
                for depth, prefixes in levels.items()
            }
            for tag, levels in tag_prefix_counts.items()
        }
        json.dump(output, f, indent=2)
        print("\nSaved tag path prefix stats to tag_path_prefix_stats.json")

    duplicates = find_duplicate_endpoint_names(spec)
    if duplicates:
        print("\nDuplicate endpoint names found:")
        for name, occurrences in duplicates.items():
            print(f"  {name}  - occurs {len(occurrences)} times")
            for path, method in occurrences:
                print(f"    {method} {path}")
    else:
        print("\nNo duplicate endpoint names found.")



if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python api_tree.py path/to/swagger.json")
    else:
        main(sys.argv[1])