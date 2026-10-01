#import "/plugins/lineage/book/template.typ": *
#show: book.with(title: "The Lake Was Always There", trim: "7x10")
#show: main-matter
#show: chapter.with("Plates", setting: "Duluth and Pike Lake", dates: "1945–1968", summary: [Photographs, with what is known about each])
#flush[Each caption says what is documented and what is inferred. Unidentified people stay unidentified.]
#plate-pair("/examples/sample-project/photos/print/P001.png", "/examples/sample-project/photos/print/P002.png",
  caption-a: "The ore dock · place from the transcript", caption-b: "The cabin · built 1964 or so", width: 2.4in)
#plate("/examples/sample-project/photos/print/P002.png", caption: "Pike Lake · date inferred", width: 4in)
