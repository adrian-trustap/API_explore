import json
from collections import defaultdict
import sys
import yaml  # add this

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



if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python api_tree.py path/to/swagger.json")
    else:
        main(sys.argv[1])