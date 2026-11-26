"""Repackage frozen lifecycle book checkpoints without decryption or economic replay."""
from . import owner_causal_source_shards as original

def main():
    original.SOURCE_RUN=45885931266
    original.SOURCE_ARTIFACT=15150477614
    original.SOURCE_BYTES=688803495
    original.SOURCE_SHA='d909c7aa4641fe31982f17b3cf49ea028778631baa1710dfdc91542634be35fc'
    # Existing partitioner retains encrypted manifest, offsets and hashes.
    original.main()
if __name__=='__main__':main()
