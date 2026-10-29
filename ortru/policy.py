"""The explicit relationship between the two independent signals.

Hafnia (language model, one answer per window) and local vision (detector samples) are separate observers.
They can disagree without either being wrong, and neither is silently converted into the other:
  * Hafnia says no, vision places a person at the region      -> `disagreement`: raise (default). Not a contradiction.
  * Hafnia says yes, vision places a person at the region      -> `corroborated`: raise (default).
  * Hafnia uncertain or its reply unusable, vision triggered   -> `unresolved`: raise (default). Never treated as no.
  * Hafnia says yes, vision saw nothing near the region        -> `hafnia_only`: not raised by default.
  * Hafnia says no, vision saw nothing                          -> `clear`.
  * Hafnia uncertain or unusable, vision saw nothing            -> `inconclusive`: not raised, shown as inconclusive.
"""

KINDS = ('disagreement', 'corroborated', 'unresolved', 'hafnia_only', 'clear', 'inconclusive')
DEFAULT_RAISE = ('disagreement', 'corroborated', 'unresolved')

LABELS = dict(
    disagreement='Hafnia saw no match, local vision did',
    corroborated='Hafnia and local vision both point to it',
    unresolved='Hafnia could not decide, local vision triggered',
    hafnia_only='Hafnia reported it, local vision saw nothing near the region',
    clear='Nothing found by either source',
    inconclusive='Hafnia gave no usable answer, local vision saw nothing')


def hafnia_outcome(record):
    """observed | not_observed | uncertain | malformed, from a saved Hafnia record. Anything unusable is `malformed`."""
    parsed = (record or {}).get('parsed') or {}
    if parsed.get('category') != 'valid_model_decision':
        return 'malformed'
    return {'supported': 'observed', 'not_observed': 'not_observed', 'uncertain': 'uncertain'}.get(parsed.get('outcome'), 'malformed')


def decide(hafnia, vision, raise_on=DEFAULT_RAISE):
    """hafnia in {observed, not_observed, uncertain, malformed}; vision in {triggered, none}. Returns kind, raised, label."""
    if hafnia not in ('observed', 'not_observed', 'uncertain', 'malformed') or vision not in ('triggered', 'none'):
        raise ValueError('Unknown signal outcome')
    unusable = hafnia in ('uncertain', 'malformed')
    if vision == 'triggered':
        kind = 'unresolved' if unusable else 'corroborated' if hafnia == 'observed' else 'disagreement'
    else:
        kind = 'inconclusive' if unusable else 'hafnia_only' if hafnia == 'observed' else 'clear'
    return dict(kind=kind, raised=kind in raise_on, label=LABELS[kind], hafnia=hafnia, vision=vision)
