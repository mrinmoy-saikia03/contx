---
description: Generate a draw.io architecture diagram by reading + reasoning about the code
argument-hint: <type: architecture|components|dataflow|deploy>
---

# /contx-diagram $ARGUMENTS

Generate a `.drawio` diagram by **reading** the code and **reasoning** about architecture.

## Steps

1. Resolve the diagram type from `$ARGUMENTS`. Default: `architecture`. Valid: `architecture`, `components`, `dataflow`, `deploy`.
2. Pick the right files to read:
   - **architecture**: top-level modules and their import graphs
   - **components**: classes and their composition / inheritance
   - **dataflow**: pipeline functions (parse → validate → transform → write)
   - **deploy**: tracked deployment manifests + the services they target
3. Use the Glob and Read tools to load those files.
4. Reason about the right groupings, hierarchy, and edges. **Do not draw every import** — only the architecturally significant ones. A good diagram fits on one page (≤30 nodes).
5. Construct draw.io mxGraph XML directly. Schema:

   ```xml
   <mxfile host="contx" type="device" version="1">
     <diagram name="contx ${type}">
       <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1200" pageHeight="800">
         <root>
           <mxCell id="0"/>
           <mxCell id="1" parent="0"/>
           <!-- vertex cells: vertex="1", parent="1", style with rounded=1;whiteSpace=wrap;html=1;fillColor=#XXXXXX;strokeColor=#666666;fontSize=11; and an <mxGeometry x= y= width= height= as="geometry"/> -->
           <!-- edge cells: edge="1", source=<id>, target=<id>, parent="1", style="endArrow=classic;html=1;rounded=1;strokeColor=#999999;" with an <mxGeometry relative="1" as="geometry"/> -->
         </root>
       </mxGraphModel>
     </diagram>
   </mxfile>
   ```

6. Layout guidance:
   - Group related nodes together visually (close coordinates).
   - Color groups distinctly. Use a small palette: `#E3F2FD`, `#FFF3E0`, `#F3E5F5`, `#E8F5E9`, `#FFFDE7`, `#FCE4EC`.
   - Dataflow runs left-to-right; hierarchy runs top-to-bottom.
   - Box width 160, height 50; space them ~80 px apart.
7. Write the XML to `.contx/diagrams/<type>.drawio`. Create the directory if needed.
8. Append a `contx_append` entry on the diagram file describing what's in it (kind=file, event=created, tags=["diagram", "claude-generated"]).

## Constraints

- One page only. If the repo is larger, pick the most important subsystem and note `(subset)` in the diagram title.
- Every edge must have semantic meaning — if you can't justify an edge in one sentence, drop it.
- Don't include test files, fixtures, or generated artifacts.

## Output

The path to the written `.drawio`, plus a 2–3 sentence summary of what the diagram shows and what was intentionally left out.
