# -*- coding: utf-8 -*-
# @Time         : 16:22 2026/6/23
# @Author       : Chris
# @Description  :
import copy
from collections import deque
from typing import Deque, Optional

from odoo import models, _

from .acl import FieldMode
from .alias import AliasNode, AliasField
from .base import IRecsReader, AclUnit, UnitKind
from .compatible import NEG2POS_OPR
from .compatible import is_api_model
from .meta import OqlMeta
from .recs import *
from .util import tn, read_object, write_object

_logger = logging.getLogger(__name__)


class FieldAccess(IRecsReader):

    model: models.Model
    """Accessing target model."""

    x2m: bool
    """Whether there is any X2Many field on the access path."""

    pre_domain: OqlDomain
    """Pre-selector domain, select some records for further filtering."""

    def __init__(self, model: models.Model, names: Iterable[str], meta: OqlMeta, pre_domain: OqlDomain = None,
                 as_: str = None, is_agg: Optional[bool] = None, _is_root=True):
        self.meta = meta
        model = model.browse()  # Make model data-inconscient.
        env = model.env
        # Parse
        names = list(names)
        as_ = as_ or '.'.join(names)
        plain_names = []
        p_recs = model
        pp_recs = None  # The recs right before p_recs in path.
        next_ = []
        b_x2m = False
        non_searchable_fields = []
        tail_alias = None
        units: List[AclUnit] = []
        i = 0
        j_alias_span_end = 0  # Alias will expand dot-path into `names`, this `j` is the index right after the expansion span.
        while i < len(names):
            name = names[i]
            # Model Field
            if hasattr(p_recs, name):
                f_meta = p_recs._fields[name]
                # Check X2Many
                if not b_x2m:
                    if f_meta.type in ('one2many', 'many2many'):
                        b_x2m = True
                # Check availability in search criteria.
                if not f_meta._description_searchable:
                    non_searchable_fields.append(name)
                plain_names.append(name)
                if i >= j_alias_span_end:
                    # Alias expansion span is not ACL unit, so we just add field outside the span.
                    units.append(AclUnit(p_recs, name, UnitKind.FIELD))
                i += 1
                pp_recs = p_recs
                p_recs = p_recs[name]
                continue
            # Alias
            alias = meta.get_alias(p_recs._name, name)
            if alias:
                if alias.is_complex:
                    if i != len(names) - 1:
                        raise Exception(f"Complex alias `{name}` can only be tail of field path. Path: `{'.'.join(names)}`")
                    tail_alias = alias
                    b_x2m = True  # Treat complex alais as X2Many field.
                    units.append(AclUnit(p_recs, name, UnitKind.ALIAS))
                    break
                else:
                    assert isinstance(alias, AliasField), \
                        f"Only `{AliasField.__name__}` could be non-complex alias. Not `{type(alias).__name__}`."
                    chips = alias.path.split('.')
                    i += 1
                    # Expand alias name path into `names`
                    names[i:i] = chips
                    j_alias_span_end = i + len(chips)
                    units.append(AclUnit(p_recs, name, UnitKind.ALIAS))
                    continue
            # Term
            domains = meta.get_domains(name)
            if domains:
                remains = names[i+1:]
                for child_domain in domains:
                    next_.append(FieldAccess(env[child_domain.model], remains, meta, child_domain, _is_root=False))
                break
            prefix = ".".join([tn(model), *plain_names])
            raise RuntimeError(_(f"Neither `%s(.%s)` is a field nor an alias nor a term. "
                                 f"Or you don't have access right to it.")
                               % (prefix, name))
        rear_field: Optional[fields.Field] = None
        if plain_names:
            rear_field_name = plain_names[-1]
            if pp_recs is None:
                if len(plain_names) == 1:
                    rear_field = model._fields[rear_field_name]  # noqa
            else:
                rear_field = pp_recs._fields[rear_field_name]  # noqa

        # Validate (.) term statement.
        rear = p_recs
        if (next_ or tail_alias) and not isinstance(rear, Model):
            raise Exception(_(f"Invalid field path `{model._name}` -> `{'.'.join(names[:i])}` (.) `{names[i]}`. "
                              f"Expect relational field before (.), got `{rear_field.type}`."))
        # Initialize instance.
        self.root = RecordSet(model, pre_domain or OqlDomain.all(model._name))
        self.model = model
        self._rear_model: Optional[Model] = rear if isinstance(rear, Model) else None
        self.names = plain_names
        self.pre_domain = pre_domain
        self.x2m = b_x2m
        self.next: List[FieldAccess] = next_
        self._non_searchable_fields = non_searchable_fields
        self._rear_field: Optional[fields.Field] = rear_field
        self._tail_alias: Optional[AliasNode] = tail_alias  # Complex alias at tail.
        self._as = as_
        self._is_root = _is_root
        self._is_agg = bool(is_agg)
        self._acl_units = units

    @property
    def is_agg(self):
        return self._is_agg

    @property
    def model_name(self):
        return self.model._name  # noqa

    @property
    def as_(self):
        return self._as

    @as_.setter
    def as_(self, value: str):
        self._as = value

    @property
    def path(self):
        names = self.names
        if self._tail_alias:
            names = names + [self._tail_alias.alias]
        return '.'.join(names)

    @property
    def expr(self) -> str:
        chips = []
        if self.pre_domain and self.pre_domain.term:
            chips.append(self.pre_domain.term.name)
        if self.path:
            chips.append(self.path)
        if self.next:
            chips.append(self.next[0].expr)
        return '.'.join(chips)

    @property
    def endswith_term(self) -> bool:
        """Whether rear of this access chain is a Term."""
        if self.next:
            return any(x.endswith_term for x in self.next)
        if self.pre_domain and self.pre_domain.term:
            return True
        return False

    @property
    def is_field(self) -> bool:
        """Whether this is a plain field access. e.g. `name`, `price`."""
        return len(self.names) == 1 and not self._tail_alias and not self.next

    @property
    def is_flat(self):
        """Whether the `next` chain is singular."""
        if len(self.next) == 0:
            return True
        elif len(self.next) == 1:
            return self.next[0].is_flat
        else:
            return False

    @property
    def is_empty(self):
        return False  # Hard coded.

    @property
    def rear_model(self) -> Optional[models.Model]:
        """Model of last field on path. If last field is not relational, returns `None`."""
        return self._rear_model

    @property
    def chain_rear_model(self):
        """The full chain's rear model. For flat chain only."""
        if len(self.next) == 0:
            return self.rear_model
        elif len(self.next) == 1:
            return self.next[0].chain_rear_model
        else:
            raise Exception(f"`chain_rear_model` is only available for flat chain.")

    @property
    def rear_field(self) -> Optional[fields.Field]:
        return self._rear_field

    @property
    def nodes(self) -> List["FieldAccess"]:
        """All field access nodes on the chain (`self` included). In BFS order."""
        nodes = []
        q: Deque[FieldAccess] = deque()
        q.append(self)
        while len(q) > 0:
            node = q.popleft()
            nodes.append(node)
            q.extend(node.next)
        return nodes

    @property
    def chain_acl_units(self) -> List[AclUnit]:
        """All ACL units on the chain."""
        return [y for x in self.nodes for y in x._acl_units]

    def eval_bin(self, opr: str, value):
        opr = " ".join(opr.split())  # Normalize spaces
        return self._eval(False, opr, value)

    def eval_una(self, opr: str):
        return self._eval(True, opr, None)

    def read(self, recs, load='_classic_read') -> list:
        """Read value from recs. Result is aligned with `recs`.
        Note: If there is any X2Many field on the field path, the result item will be list type."""
        # Check
        if recs._name != self.root.name:
            raise Exception(f"Expect `{self.root.name}` records, got `{recs._name}`.")
        # Read
        path = '.'.join(self.names)
        recs.mapped(path)  # Prefetch.
        tail_alias = self._tail_alias
        if tail_alias:
            res = [tail_alias.read(read_object(x, path)) for x in recs]
        elif self._rear_field and not self._rear_field.relational:
            # Optimize reading performance for non-relational rear field.
            res = [x.mapped(path) for x in recs]
        else:
            # Use `Model.read` instead of `Model.map` to align with odoo's building `read` behavior.
            chips = path.rsplit('.', 1)
            prefix_path, field = ("", chips[0]) if len(chips) == 1 else chips
            res = [[y[field] for y in read_object(x, prefix_path).read([field], load)] for x in recs]
        if not self.x2m:  # Flat result for non-x2many path.
            res = [x[0] if x else None for x in res]
        if self.is_agg:
            res = [res]
        return res

    def write(self, recs, value):
        for rec in recs:
            write_object(rec, self.path, value)

    def _eval(self, una: bool, opr: str, value):
        """
        Core eval function.
        :param una: True: Unary, False: Binary
        :param opr: Unary or binary operator
        :param value: Could be None in unary model
        :return: Evaluation result
        """
        # Check
        if self._non_searchable_fields:
            raise Exception(_("Can't search with expression `%s %s %s`. "
                              "Some fields in expression are not searchable: %s. "
                              "Please contact administrator for help or use a difference field.") %
                            (self.expr, opr, value, self._non_searchable_fields))
        if self._tail_alias:
            raise Exception(_("Can't search with expression `%s %s %s`. "
                              "Complex alias can't be used to search. Complex alias: %s") %
                            (self.expr, opr, value, self._tail_alias.alias))
        # Eval
        root = self.root
        model = self.model
        names = self.names
        pre_domain = self.pre_domain
        is_root = self._is_root
        if self.next:  # Branch node
            dot_opr = "in"
            if is_root and opr in NEG2POS_OPR:  # Negative expression.
                opr = NEG2POS_OPR[opr]  # To positive operator.
                dot_opr = "not in"  # Reverse logic at root `has` logic check.
            meta = self.meta
            rear_model = self._rear_model
            list_rec_set_y = []
            for child in self.next:
                rec_sets = child._eval(una, opr, value)
                for rec_set in rec_sets:
                    if rear_model._name == rec_set.name:
                        fullpath = ".".join(names)
                    else:
                        path = meta.get_path(rear_model._name, ".", rec_set)
                        fullpath = ".".join([*names, path])
                    domain = OqlDomain(f"{fullpath} {dot_opr} {rec_set.domain}",
                                       root.name,
                                       [(fullpath, dot_opr, rec_set.get_recs().ids)])
                    list_rec_set_y.append(RecordSet(model, domain))
            return RecordSets(list_rec_set_y)
        elif una:
            if opr == "bool":
                if names:
                    # e.g. WHERE product_id.active
                    fullpath = ".".join(names)
                    domain = OqlDomain(f"{opr}({fullpath})", root.name, [(fullpath, "!=", False)])
                    if pre_domain:
                        domain = OqlDomain.and_(pre_domain, domain)
                    return RecordSets([RecordSet(model, domain)])
                else:
                    # e.g. WHERE Waterproof.
                    return RecordSets([RecordSet(model, pre_domain)])
            else:
                raise NotImplementedError(f"Unary operator `{opr}({tn(self.model)})` not implemented.")
        else:
            # 1 Prepare meta.
            value_domain = None  # Only RecordSet value has domain info.
            if isinstance(value, RecordSet):
                value_domain = value.domain
                value = value.get_recs()
            fullpath = ".".join(names) if names else None
            # 2 Try customized `__oql_bin__` first.
            oql_bin = model.__oql_bin__  # noqa
            if pre_domain and not is_api_model(oql_bin):
                recs = self.model.search(pre_domain.domain)  # Load record automatically for recordset level method.
                oql_bin = recs.__oql_bin__
            res = oql_bin(pre_domain, fullpath, opr, value, value_domain)
            if res is not None:  # `None` means fall through to built-in logic.
                if not isinstance(res, models.Model):
                    raise Exception(f"`{root.name}.__oql_bin__` returns `{type(res)}` data, but recordset expected.")
                return RecordSets(
                    [RecordSet(res, OqlDomain("__oql_bin__", res._name, [("id", "in", res.ids)]))])
            # 3 Try built-in binary logic.
            if not fullpath:
                fullpath = self.meta.get_path(root.name, opr, value, True)  # Try finding shorthand.
            domain = OqlDomain(f"{fullpath} {opr} {value}", root.name, [(fullpath, opr, value)])
            if pre_domain:
                domain = OqlDomain.and_(pre_domain, domain)
            return RecordSets([RecordSet(root.model, domain)])

    def flat(self) -> List["FieldAccess"]:
        """Product with `next` field accesses recursively to make a full Cartesian set.
        Note: All the result objects are copies."""
        flatted_fas: List[FieldAccess] = []
        if self.next:
            for next_fa in self.next:
                for next_flatted_fa in next_fa.flat():
                    this = copy.copy(self)
                    this.next = [next_flatted_fa]
                    flatted_fas.append(this)
        else:
            flatted_fas.append(copy.copy(self))
        return flatted_fas

    def check_perm(self, mode: FieldMode):
        acl = self.meta.acl
        mac = acl[self.model_name]
        return mac.check_path(self.path, mode)

    def __str__(self):
        return f"{type(self).__name__}({self.path}, next[{len(self.next)}])"

    def __repr__(self):
        return str(self)
