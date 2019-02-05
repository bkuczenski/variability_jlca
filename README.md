# Market Variability in Ecoinvent
Work demonstrating variability in LCIA results for ecoinvent systems outside of parametric uncertainty. The work uses `lca-tools` to compute dynamic range of market mixes / review market mixes and `brightway2` is used for Monte Carlo simulations of ecoinvent.  MCS runs are saved by default to disk as json files by UUID, so that a statistical record will continue to grow until the file is deleted.

JuPYter notebooks

To run catalog-based first:
 - '0. Setup Catalog.ipynb'
 - 'DEMO-0'
 
To run brightway 2:
 - 'DEMO-1' and just have ecoinvent named the same way I do
 
Then:
 - 'DEMO-2' does demonstration figures comparing the discrete and continuous probability distributions
 - 'DEMO-3' measures the extent / utilization of markets in ecoinvent (conseq left out for some reason :( )
 - 'Editorial image'  does the figure from the editorial.
 - 'Freight transport study' ongoing for paper- but it seems optimistic for a GLO model (bc pedigree 12241 or whatever)

Other stuff I should just delete.
